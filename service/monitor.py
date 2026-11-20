"""GoreeCloud Monitor: dependency-free self-hosted HTTP/TCP uptime service.

The service deliberately defaults to loopback binding, private monitors, and
blocked private-network probes until an operator explicitly opts in.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hmac
import http.client
import ipaddress
import json
import os
import signal
import socket
import sqlite3
import ssl
import threading
import time
import urllib.parse
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def setting(name, default):
    return os.environ.get(name, default)


def connect(path):
    db = sqlite3.connect(str(path), timeout=15)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA busy_timeout=15000")
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA journal_mode=WAL")
    return db


def initialize(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with connect(path) as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS monitors (
                id TEXT PRIMARY KEY, name TEXT NOT NULL,
                target TEXT NOT NULL, kind TEXT NOT NULL,
                interval_s INTEGER NOT NULL, timeout_s INTEGER NOT NULL,
                expected_status INTEGER NOT NULL, public INTEGER NOT NULL DEFAULT 0,
                active INTEGER NOT NULL DEFAULT 1, state TEXT NOT NULL DEFAULT 'pending',
                last_checked INTEGER, last_latency_ms INTEGER,
                created_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS checks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                monitor_id TEXT NOT NULL REFERENCES monitors(id) ON DELETE CASCADE,
                checked_at INTEGER NOT NULL, ok INTEGER NOT NULL,
                latency_ms INTEGER NOT NULL, detail TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS checks_recent
                ON checks(monitor_id, checked_at DESC);
            CREATE TABLE IF NOT EXISTS incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                monitor_id TEXT NOT NULL REFERENCES monitors(id) ON DELETE CASCADE,
                started_at INTEGER NOT NULL, resolved_at INTEGER
            );
            CREATE INDEX IF NOT EXISTS incidents_open
                ON incidents(monitor_id, resolved_at);
        """)


def parse_monitor(payload):
    if not isinstance(payload, dict):
        raise ValueError("Expected a JSON object")
    name = payload.get("name")
    target = payload.get("target")
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 100:
        raise ValueError("Name must contain 1-100 characters")
    if not isinstance(target, str) or len(target) > 2048:
        raise ValueError("Invalid target")
    p = urllib.parse.urlsplit(target)
    if p.scheme not in ("http", "https", "tcp") or not p.hostname:
        raise ValueError("Target must use http://, https:// or tcp://")
    if p.username or p.password or p.fragment:
        raise ValueError("Userinfo and fragments are forbidden")
    try:
        port = p.port
    except ValueError as exc:
        raise ValueError("Invalid port") from exc
    if p.scheme == "tcp" and (not port or p.path or p.query):
        raise ValueError("TCP targets require a port and no path")
    if p.scheme in ("http", "https") and not (p.hostname and p.hostname.strip(".")):
        raise ValueError("Invalid hostname")
    interval = payload.get("interval_s", 60)
    timeout = payload.get("timeout_s", 8)
    expected = payload.get("expected_status", 200)
    if type(interval) is not int or not 15 <= interval <= 86400:
        raise ValueError("Interval must be 15-86400 seconds")
    if type(timeout) is not int or not 1 <= timeout <= 30:
        raise ValueError("Timeout must be 1-30 seconds")
    if type(expected) is not int or not 100 <= expected <= 599:
        raise ValueError("Expected HTTP status must be 100-599")
    if type(payload.get("public", False)) is not bool:
        raise ValueError("Public must be a boolean")
    return dict(name=name.strip(), target=target, kind=p.scheme,
                interval_s=interval, timeout_s=timeout, expected_status=expected,
                public=int(payload.get("public", False)))


def permitted_address(host, port, allow_private):
    records = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    addresses = sorted(set(item[4][0] for item in records))
    if not addresses:
        raise OSError("No DNS results")
    # Reject the entire DNS answer, not just the selected address, to avoid
    # mixed public/private answers being used as an SSRF escape.
    if not allow_private and any(not ipaddress.ip_address(ip).is_global for ip in addresses):
        raise ValueError("Target resolves to a blocked non-public IP address")
    return addresses[0]


def probe(monitor, allow_private=False):
    started = time.monotonic()
    p = urllib.parse.urlsplit(monitor["target"])
    port = p.port or (443 if p.scheme == "https" else 80)
    try:
        ip = permitted_address(p.hostname, port, allow_private)
        if p.scheme == "tcp":
            with socket.create_connection((ip, port), timeout=monitor["timeout_s"]):
                pass
            ok, detail = True, "TCP connection established"
        else:
            raw = socket.create_connection((ip, port), timeout=monitor["timeout_s"])
            try:
                if p.scheme == "https":
                    raw = ssl.create_default_context().wrap_socket(
                        raw, server_hostname=p.hostname
                    )
                connection = http.client.HTTPConnection(
                    p.hostname, port, timeout=monitor["timeout_s"]
                )
                connection.sock = raw
                path = urllib.parse.urlunsplit(("", "", p.path or "/", p.query, ""))
                connection.request("GET", path, headers={
                    "User-Agent": "GoreeCloud-Monitor/0.1",
                    "Accept": "*/*", "Connection": "close"
                })
                response = connection.getresponse()
                ok = response.status == monitor["expected_status"]
                detail = f"HTTP {response.status}"
                response.close()
            finally:
                raw.close()
        return ok, max(0, round((time.monotonic() - started) * 1000)), detail
    except (OSError, ValueError, ssl.SSLError, http.client.HTTPException) as exc:
        # Error detail is stored only on authenticated admin endpoints.
        return False, max(0, round((time.monotonic() - started) * 1000)), (
            f"{type(exc).__name__}: {str(exc)[:240]}"
        )


class MonitorService:
    def __init__(self, db_path, api_token="", allow_private=False):
        self.path = db_path
        self.api_token = api_token
        self.allow_private = allow_private
        initialize(self.path)
        self.pool = concurrent.futures.ThreadPoolExecutor(max_workers=4)
        self.inflight = set()
        self.lock = threading.Lock()
        self.shutdown = threading.Event()

    def create(self, data):
        item = parse_monitor(data)
        item["id"] = str(uuid.uuid4())
        item["created_at"] = int(time.time())
        with connect(self.path) as db:
            db.execute("""
                INSERT INTO monitors (id,name,target,kind,interval_s,timeout_s,
                  expected_status,public,created_at)
                VALUES (:id,:name,:target,:kind,:interval_s,:timeout_s,
                  :expected_status,:public,:created_at)
            """, item)
        return item["id"]

    def list_monitors(self, public=False):
        with connect(self.path) as db:
            sql = "SELECT * FROM monitors"
            if public:
                sql += " WHERE public=1 AND active=1"
            sql += " ORDER BY name COLLATE NOCASE"
            rows = [dict(row) for row in db.execute(sql)]
        if public:
            for row in rows:
                for key in ("target", "kind", "timeout_s", "expected_status", "created_at"):
                    row.pop(key, None)
        return rows

    def status(self):
        monitors = self.list_monitors(public=True)
        with connect(self.path) as db:
            public_incidents = [dict(r) for r in db.execute("""
                SELECT i.id, m.name AS monitor_name, i.started_at
                FROM incidents i JOIN monitors m ON m.id=i.monitor_id
                WHERE i.resolved_at IS NULL AND m.public=1 AND m.active=1
                ORDER BY i.started_at DESC LIMIT 50
            """)]
        return {
            "service": "GoreeCloud Monitor",
            "updated_at": int(time.time()),
            "summary": {
                "total": len(monitors),
                "up": sum(m["state"] == "up" for m in monitors),
                "down": sum(m["state"] == "down" for m in monitors),
                "pending": sum(m["state"] == "pending" for m in monitors),
            },
            "monitors": monitors,
            "incidents": public_incidents,
        }

    def check(self, monitor_id):
        with connect(self.path) as db:
            row = db.execute("SELECT * FROM monitors WHERE id=? AND active=1",
                             (monitor_id,)).fetchone()
        if not row:
            return None
        monitor = dict(row)
        ok, latency, detail = probe(monitor, self.allow_private)
        moment = int(time.time())
        new_state = "up" if ok else "down"
        with connect(self.path) as db:
            previous = db.execute("SELECT state FROM monitors WHERE id=?",
                                  (monitor_id,)).fetchone()
            if not previous:
                return None
            db.execute("""UPDATE monitors SET state=?, last_checked=?,
                       last_latency_ms=? WHERE id=?""",
                       (new_state, moment, latency, monitor_id))
            db.execute("""INSERT INTO checks(monitor_id,checked_at,ok,latency_ms,detail)
                          VALUES(?,?,?,?,?)""",
                       (monitor_id, moment, int(ok), latency, detail))
            if new_state == "down" and previous["state"] != "down":
                db.execute("""INSERT INTO incidents(monitor_id,started_at)
                              VALUES(?,?)""", (monitor_id, moment))
            elif new_state == "up" and previous["state"] == "down":
                db.execute("""UPDATE incidents SET resolved_at=?
                              WHERE monitor_id=? AND resolved_at IS NULL""",
                           (moment, monitor_id))
            # Keep bounded history: last 5000 entries per monitor.
            db.execute("""DELETE FROM checks WHERE monitor_id=? AND id NOT IN
                          (SELECT id FROM checks WHERE monitor_id=?
                           ORDER BY id DESC LIMIT 5000)""",
                       (monitor_id, monitor_id))
        return {"monitor_id": monitor_id, "state": new_state,
                "latency_ms": latency, "detail": detail, "checked_at": moment}

    def history(self, monitor_id):
        with connect(self.path) as db:
            exists = db.execute("SELECT 1 FROM monitors WHERE id=?",
                                (monitor_id,)).fetchone()
            if not exists:
                return None
            return [dict(r) for r in db.execute("""
                SELECT checked_at,ok,latency_ms,detail
                FROM checks WHERE monitor_id=?
                ORDER BY id DESC LIMIT 200
            """, (monitor_id,))]

    def remove(self, monitor_id):
        with connect(self.path) as db:
            cur = db.execute("DELETE FROM monitors WHERE id=?", (monitor_id,))
            return cur.rowcount > 0

    def run_scheduler(self):
        while not self.shutdown.wait(1):
            now = int(time.time())
            with connect(self.path) as db:
                due = [r["id"] for r in db.execute("""
                    SELECT id FROM monitors WHERE active=1
                    AND (last_checked IS NULL OR last_checked + interval_s <= ?)
                """, (now,))]
            for monitor_id in due:
                with self.lock:
                    if monitor_id in self.inflight:
                        continue
                    self.inflight.add(monitor_id)
                future = self.pool.submit(self.check, monitor_id)
                future.add_done_callback(
                    lambda _, mid=monitor_id: self.mark_finished(mid)
                )

    def mark_finished(self, monitor_id):
        with self.lock:
            self.inflight.discard(monitor_id)

    def close(self):
        self.shutdown.set()
        self.pool.shutdown(wait=True)


def handler_factory(service):
    class Handler(BaseHTTPRequestHandler):
        server_version = "GoreeCloudMonitor/0.1"

        def send(self, code, payload, content_type="application/json"):
            body = (json.dumps(payload, separators=(",", ":")).encode()
                    if content_type == "application/json" else payload.encode())
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Frame-Options", "DENY")
            self.end_headers()
            self.wfile.write(body)

        def authorized(self):
            header = self.headers.get("Authorization", "")
            return bool(service.api_token) and hmac.compare_digest(
                header.encode(), ("Bearer " + service.api_token).encode()
            )

        def require_admin(self):
            if not service.api_token:
                self.send(503, {"error": "Set MONITOR_API_TOKEN to enable admin API"})
                return False
            if not self.authorized():
                self.send(401, {"error": "Unauthorized"})
                return False
            return True

        def do_GET(self):
            path = urllib.parse.urlsplit(self.path).path
            if path == "/healthz":
                return self.send(200, {"status": "ok"})
            if path == "/api/v1/status":
                return self.send(200, service.status())
            if not self.require_admin():
                return
            if path == "/api/v1/monitors":
                return self.send(200, {"monitors": service.list_monitors()})
            if path == "/metrics":
                rows = service.list_monitors()
                text = ("# HELP goreecloud_monitor_up Whether each monitor is up\n"
                        "# TYPE goreecloud_monitor_up gauge\n")
                for row in rows:
                    text += (f'goreecloud_monitor_up{{id="{row["id"]}"}} '
                             f'{int(row["state"] == "up")}\n')
                return self.send(200, text, "text/plain; version=0.0.4")
            parts = path.strip("/").split("/")
            if len(parts) == 5 and parts[:3] == ["api", "v1", "monitors"] and parts[4] == "history":
                result = service.history(parts[3])
                return self.send(200, {"checks": result}) if result is not None else self.send(404, {"error": "Not found"})
            self.send(404, {"error": "Not found"})

        def do_POST(self):
            if not self.require_admin():
                return
            path = urllib.parse.urlsplit(self.path).path
            if path == "/api/v1/monitors":
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if length < 1 or length > 16384:
                        return self.send(413, {"error": "Body size must be 1-16384 bytes"})
                    data = json.loads(self.rfile.read(length))
                    monitor_id = service.create(data)
                    return self.send(201, {"id": monitor_id})
                except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                    return self.send(400, {"error": str(exc)})
            parts = path.strip("/").split("/")
            if len(parts) == 5 and parts[:3] == ["api", "v1", "monitors"] and parts[4] == "check":
                result = service.check(parts[3])
                return self.send(200, result) if result else self.send(404, {"error": "Not found"})
            self.send(404, {"error": "Not found"})

        def do_DELETE(self):
            if not self.require_admin():
                return
            parts = urllib.parse.urlsplit(self.path).path.strip("/").split("/")
            if len(parts) == 4 and parts[:3] == ["api", "v1", "monitors"]:
                if service.remove(parts[3]):
                    return self.send(200, {"deleted": True})
            self.send(404, {"error": "Not found"})

        def log_message(self, fmt, *args):
            # Do not log authorization data, targets, or request bodies.
            print(f"{self.address_string()} - {fmt % args}", flush=True)

    return Handler


def main():
    parser = argparse.ArgumentParser(description="GoreeCloud Monitor")
    parser.add_argument("--host", default=setting("MONITOR_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(setting("MONITOR_PORT", "8765")))
    parser.add_argument("--db", default=setting("MONITOR_DB", "./data/monitor.db"))
    args = parser.parse_args()
    token = setting("MONITOR_API_TOKEN", "")
    if token and len(token) < 32:
        parser.error("MONITOR_API_TOKEN must contain at least 32 characters")
    service = MonitorService(args.db, token,
                             allow_private=setting("MONITOR_ALLOW_PRIVATE_TARGETS", "0") == "1")
    scheduler = threading.Thread(target=service.run_scheduler, daemon=True)
    scheduler.start()
    server = ThreadingHTTPServer((args.host, args.port), handler_factory(service))
    server.daemon_threads = True
    print(f"GoreeCloud Monitor listening on {args.host}:{args.port}", flush=True)
    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        service.close()


if __name__ == "__main__":
    main()
