"""GoreeCloud Monitor 0.1.0: dependency-free private monitoring server."""
from __future__ import annotations

import hashlib
import hmac
import http.client
import http.cookies
import http.server
import ipaddress
import json
import os
from pathlib import Path
import secrets
import socket
import sqlite3
import ssl
import threading
import time
from xml.sax.saxutils import escape as xml_escape
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timezone
from urllib.parse import urlsplit

BASE = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("GC_DATA_DIR", "./data")).resolve()
DATABASE = DATA_DIR / "monitor.sqlite3"
HOST = os.environ.get("GC_HOST", "127.0.0.1")
PORT = int(os.environ.get("GC_PORT", "3001"))
ALLOW_PRIVATE = os.environ.get("GC_ALLOW_PRIVATE_TARGETS", "0") == "1"
COOKIE_SECURE = os.environ.get("GC_COOKIE_SECURE", "0") == "1"
SESSION_LIFETIME = 8 * 3600
SESSIONS: dict[str, tuple[float, str]] = {}
SESSIONS_LOCK = threading.Lock()
LOGIN_ATTEMPTS: dict[str, list[float]] = {}
LOGIN_LOCK = threading.Lock()
STOP = threading.Event()


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def password() -> str:
    file_path = os.environ.get("GC_ADMIN_PASSWORD_FILE")
    if file_path:
        value = Path(file_path).read_text(encoding="utf-8").rstrip("\r\n")
    else:
        value = os.environ.get("GC_ADMIN_PASSWORD", "")
    if len(value) < 12:
        raise RuntimeError("Set GC_ADMIN_PASSWORD_FILE or GC_ADMIN_PASSWORD (minimum 12 characters)")
    return value


@contextmanager
def db():
    con = sqlite3.connect(DATABASE, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA busy_timeout=30000")
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def initialize():
    DATA_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        DATA_DIR.chmod(0o700)
    except OSError:
        pass
    with db() as con:
        con.executescript("""
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS monitors (
          id INTEGER PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL,
          target TEXT NOT NULL, interval_seconds INTEGER NOT NULL,
          timeout_seconds INTEGER NOT NULL, expected_code INTEGER NOT NULL DEFAULT 200,
          keyword TEXT NOT NULL DEFAULT '', public INTEGER NOT NULL DEFAULT 0,
          active INTEGER NOT NULL DEFAULT 1, token_hash TEXT UNIQUE,
          state TEXT NOT NULL DEFAULT 'pending', last_check TEXT,
          latency_ms REAL, failures INTEGER NOT NULL DEFAULT 0,
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS heartbeats (
          id INTEGER PRIMARY KEY, monitor_id INTEGER NOT NULL REFERENCES monitors(id) ON DELETE CASCADE,
          time TEXT NOT NULL, state TEXT NOT NULL, latency_ms REAL, detail TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS heartbeat_lookup ON heartbeats(monitor_id, time DESC);
        CREATE TABLE IF NOT EXISTS incidents (
          id INTEGER PRIMARY KEY, monitor_id INTEGER REFERENCES monitors(id) ON DELETE SET NULL,
          title TEXT NOT NULL, description TEXT NOT NULL, status TEXT NOT NULL,
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL, public INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS maintenance (
          id INTEGER PRIMARY KEY, title TEXT NOT NULL, description TEXT NOT NULL,
          starts_at TEXT NOT NULL, ends_at TEXT NOT NULL, created_at TEXT NOT NULL
        );
        """)


def valid_ip(value: str, allow_private: bool = ALLOW_PRIVATE) -> bool:
    ip = ipaddress.ip_address(value.split("%", 1)[0])
    if ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_unspecified or ip.is_reserved:
        return False
    # Metadata endpoints must remain inaccessible even with private probes.
    if ip == ipaddress.ip_address("169.254.169.254"):
        return False
    return allow_private or ip.is_global


def addresses(host: str, port: int, allow_private: bool = ALLOW_PRIVATE) -> list[tuple]:
    try:
        results = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError("Hostname could not be resolved") from exc
    if not results or any(not valid_ip(r[4][0], allow_private) for r in results):
        raise ValueError("Target resolves to an address excluded by the network policy")
    return results


def validate_monitor(spec: dict, allow_private: bool = ALLOW_PRIVATE) -> dict:
    if not isinstance(spec, dict):
        raise ValueError("Monitor must be an object")
    name = str(spec.get("name", "")).strip()
    kind = str(spec.get("kind", "")).lower().strip()
    target = str(spec.get("target", "")).strip()
    if not name or len(name) > 100 or any(ord(c) < 32 for c in name):
        raise ValueError("Name must contain 1–100 printable characters")
    if kind not in ("http", "tcp", "dns", "push"):
        raise ValueError("Supported types: HTTP, TCP, DNS, Push")
    try:
        interval = int(spec.get("interval_seconds", 60))
        timeout = int(spec.get("timeout_seconds", 8))
        expected_code = int(spec.get("expected_code", 200))
    except (ValueError, TypeError):
        raise ValueError("Invalid numeric monitor setting")
    if not 20 <= interval <= 86400 or not 1 <= timeout <= 30 or not 100 <= expected_code <= 599:
        raise ValueError("Invalid interval, timeout, or expected HTTP code")
    keyword = str(spec.get("keyword", ""))
    if len(keyword) > 200:
        raise ValueError("Keyword is too long")
    if kind == "http":
        parsed = urlsplit(target)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise ValueError("HTTP monitor requires an http:// or https:// URL")
        if parsed.username or parsed.password or parsed.fragment:
            raise ValueError("Credentials and fragments are not permitted in monitor URLs")
        try:
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
        except ValueError as exc:
            raise ValueError("Invalid URL port") from exc
        if port not in range(1, 65536):
            raise ValueError("Invalid URL port")
        addresses(parsed.hostname, port, allow_private)
    elif kind == "tcp":
        host, sep, port_text = target.rpartition(":")
        if not sep or not host or not port_text.isdigit() or not 1 <= int(port_text) <= 65535:
            raise ValueError("TCP target must be host:port")
        addresses(host.strip("[]"), int(port_text), allow_private)
    elif kind == "dns":
        if not target or len(target) > 253 or any(x in target for x in ("/", ":", " ")):
            raise ValueError("DNS target must be a hostname")
    else:
        target = ""
    return {
        "name": name, "kind": kind, "target": target,
        "interval_seconds": interval, "timeout_seconds": timeout,
        "expected_code": expected_code, "keyword": keyword,
        "public": int(spec.get("public", False) is True)
    }


def pinned_http_probe(target: str, timeout: int, expected_code: int, keyword: str) -> None:
    """Connect to validated IP only; TLS certificate verifies original hostname."""
    parts = urlsplit(target)
    port = parts.port or (443 if parts.scheme == "https" else 80)
    infos = addresses(parts.hostname, port)
    family, _kind, _proto, _canonical, sockaddr = infos[0]
    connection = http.client.HTTPConnection(parts.hostname, port, timeout=timeout)
    raw_sock = socket.socket(family, socket.SOCK_STREAM)
    try:
        raw_sock.settimeout(timeout)
        raw_sock.connect(sockaddr)
        if parts.scheme == "https":
            connection.sock = ssl.create_default_context().wrap_socket(
                raw_sock, server_hostname=parts.hostname
            )
        else:
            connection.sock = raw_sock
        target_path = parts.path or "/"
        if parts.query:
            target_path += "?" + parts.query
        connection.request("GET", target_path, headers={
            "Host": parts.netloc, "User-Agent": "GoreeCloud-Monitor/0.1",
            "Connection": "close"
        })
        response = connection.getresponse()
        if response.status != expected_code:
            raise ValueError("Unexpected HTTP status")
        if keyword and keyword.encode("utf-8") not in response.read(262144):
            raise ValueError("Expected keyword not found")
    finally:
        connection.close()
        raw_sock.close()


def probe(m: dict) -> tuple[str, float | None, str]:
    started = time.monotonic()
    kind, target, timeout = m["kind"], m["target"], m["timeout_seconds"]
    try:
        if kind == "http":
            pinned_http_probe(target, timeout, m["expected_code"], m["keyword"])
        elif kind == "tcp":
            hostname, _, p = target.rpartition(":")
            infos = addresses(hostname.strip("[]"), int(p))
            with socket.socket(infos[0][0], socket.SOCK_STREAM) as sock:
                sock.settimeout(timeout)
                sock.connect(infos[0][4])
        elif kind == "dns":
            infos = addresses(target, 443)
            if not infos:
                raise ValueError("No DNS results")
        else:
            return ("pending", None, "Awaiting push heartbeat")
        return ("up", round((time.monotonic() - started) * 1000, 2), "OK")
    except Exception as exc:
        return ("down", None, type(exc).__name__)


def save_heartbeat(monitor_id: int, state: str, latency: float | None, detail: str):
    with db() as con:
        row = con.execute("SELECT state, failures, active FROM monitors WHERE id=?", (monitor_id,)).fetchone()
        if row is None or not row["active"]:
            return
        failures = 0 if state == "up" else row["failures"] + 1
        effective = "down" if state == "down" and failures >= 2 else ("up" if state == "up" else row["state"])
        con.execute("""UPDATE monitors SET state=?, failures=?, latency_ms=?, last_check=? WHERE id=?""",
                    (effective, failures, latency, utcnow(), monitor_id))
        con.execute("""INSERT INTO heartbeats(monitor_id,time,state,latency_ms,detail) VALUES(?,?,?,?,?)""",
                    (monitor_id, utcnow(), state, latency, detail[:120]))
        # Retain a bounded history in this initial implementation.
        con.execute("""DELETE FROM heartbeats WHERE monitor_id=? AND id NOT IN
                    (SELECT id FROM heartbeats WHERE monitor_id=? ORDER BY id DESC LIMIT 2000)""",
                    (monitor_id, monitor_id))


def active_maintenance() -> bool:
    now = utcnow()
    with db() as con:
        return con.execute("SELECT 1 FROM maintenance WHERE starts_at<=? AND ends_at>=? LIMIT 1",
                           (now, now)).fetchone() is not None


def monitor_list(public: bool = False) -> list[dict]:
    with db() as con:
        sql = "SELECT id,name,kind,target,interval_seconds,timeout_seconds,expected_code,keyword,public,active,state,last_check,latency_ms,created_at FROM monitors"
        if public:
            sql = "SELECT id,name,kind,public,active,state,last_check,latency_ms FROM monitors WHERE public=1"
        rows = [dict(x) for x in con.execute(sql + " ORDER BY id DESC").fetchall()]
        for row in rows:
            row["public"] = bool(row["public"])
            row["active"] = bool(row["active"])
            if active_maintenance():
                row["display_state"] = "maintenance"
            else:
                row["display_state"] = row["state"] if row["active"] else "paused"
        return rows


class Scheduler(threading.Thread):
    def __init__(self):
        super().__init__(name="goreecloud-scheduler", daemon=True)
        self.running = set()
        self.lock = threading.Lock()
        self.pool = ThreadPoolExecutor(max_workers=8, thread_name_prefix="probe")

    def check(self, monitor: dict):
        try:
            state, latency, detail = probe(monitor)
            if state != "pending":
                save_heartbeat(monitor["id"], state, latency, detail)
        finally:
            with self.lock:
                self.running.discard(monitor["id"])

    def run(self):
        next_run: dict[int, float] = {}
        while not STOP.is_set():
            try:
                with db() as con:
                    rows = [dict(r) for r in con.execute("SELECT * FROM monitors WHERE active=1 AND kind!='push'")]
                now = time.monotonic()
                for m in rows:
                    if now >= next_run.get(m["id"], 0):
                        with self.lock:
                            if m["id"] in self.running:
                                continue
                            self.running.add(m["id"])
                        next_run[m["id"]] = now + m["interval_seconds"]
                        self.pool.submit(self.check, m)
                for mid in list(next_run):
                    if mid not in {m["id"] for m in rows}:
                        next_run.pop(mid, None)
                # Push monitors use a separate timeout test; missed heartbeats are down.
                with db() as con:
                    pushes = [dict(r) for r in con.execute("SELECT * FROM monitors WHERE kind='push' AND active=1")]
                for m in pushes:
                    if m["last_check"]:
                        try:
                            age = (datetime.now(timezone.utc) - datetime.fromisoformat(m["last_check"])).total_seconds()
                            if age > m["interval_seconds"] * 2 and m["state"] != "down":
                                save_heartbeat(m["id"], "down", None, "Heartbeat missed")
                        except ValueError:
                            pass
            except Exception:
                # Scheduler must remain alive after database errors.
                pass
            STOP.wait(2)


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "GoreeCloudMonitor/0.1"

    def log_message(self, fmt, *args):
        # Avoid logging target URLs, tokenized push paths, or password material.
        print("monitor request:", self.command, self.client_address[0], self.path.split("?")[0].split("/")[1:2], flush=True)

    def send(self, status: int, payload, *, cookie: str | None = None):
        body = json.dumps(payload, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(body)

    def send_text(self, status: int, body: str, mime: str):
        payload = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'none'; sandbox")
        self.end_headers()
        self.wfile.write(payload)

    def cookie_options(self) -> str:
        return "; HttpOnly; SameSite=Strict; Path=/" + ("; Secure" if COOKIE_SECURE else "")

    def read_json(self) -> dict:
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 16384:
                raise ValueError("JSON request size must be 1–16384 bytes")
            payload = json.loads(self.rfile.read(size))
            if not isinstance(payload, dict):
                raise ValueError("Expected JSON object")
            return payload
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Invalid JSON request") from exc

    def session(self):
        raw = self.headers.get("Cookie", "")
        cookie = http.cookies.SimpleCookie()
        try:
            cookie.load(raw)
        except http.cookies.CookieError:
            return None
        sid = cookie.get("gc_session")
        if sid is None:
            return None
        with SESSIONS_LOCK:
            session = SESSIONS.get(sid.value)
        if session and session[0] > time.time():
            return session
        return None

    def protected(self, write=False) -> bool:
        session = self.session()
        if not session:
            self.send(401, {"error": "Sign in required"})
            return False
        if write and not hmac.compare_digest(self.headers.get("X-CSRF-Token", ""), session[1]):
            self.send(403, {"error": "Invalid anti-CSRF token"})
            return False
        return True

    def static(self, path: str):
        names = {"/": ("web/index.html", "text/html; charset=utf-8"),
                 "/status": ("web/index.html", "text/html; charset=utf-8"),
                 "/assets/app.js": ("web/app.js", "application/javascript; charset=utf-8"),
                 "/assets/style.css": ("web/style.css", "text/css; charset=utf-8")}
        if path not in names:
            return self.send(404, {"error": "Not found"})
        name, mime = names[path]
        body = (BASE / name).read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; form-action 'self'; base-uri 'none'; frame-ancestors 'none'")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/healthz":
            return self.send(200, {"ok": True})
        if path in ("/", "/status", "/assets/app.js", "/assets/style.css"):
            return self.static(path)
        if path == "/api/public":
            with db() as con:
                incidents = [dict(r) for r in con.execute(
                    "SELECT id,title,description,status,created_at,updated_at FROM incidents WHERE public=1 ORDER BY id DESC LIMIT 25")]
                maintenance = [dict(r) for r in con.execute(
                    "SELECT title,description,starts_at,ends_at FROM maintenance WHERE ends_at>=? ORDER BY starts_at LIMIT 15", (utcnow(),))]
            return self.send(200, {"monitors": monitor_list(public=True), "incidents": incidents,
                                   "maintenance": maintenance})
        if path == "/status.rss":
            with db() as con:
                rows = [dict(r) for r in con.execute(
                    "SELECT title,description,updated_at FROM incidents WHERE public=1 ORDER BY id DESC LIMIT 25")]
            items = "".join("<item><title>" + xml_escape(r["title"]) + "</title><description>" +
                            xml_escape(r["description"]) + "</description><pubDate>" +
                            xml_escape(r["updated_at"]) + "</pubDate></item>" for r in rows)
            body = '<?xml version="1.0" encoding="UTF-8"?>' + (
                '<rss version="2.0"><channel><title>GoreeCloud Monitor incidents</title>'
                '<description>Public incident updates</description>' + items + '</channel></rss>')
            return self.send_text(200, body, "application/rss+xml; charset=utf-8")
        if path.startswith("/badge/") and path.endswith(".svg"):
            try:
                mid = int(path.split("/")[-1].removesuffix(".svg"))
            except ValueError:
                return self.send(404, {"error": "Not found"})
            with db() as con:
                m = con.execute("SELECT state,active FROM monitors WHERE id=? AND public=1", (mid,)).fetchone()
            if m is None:
                return self.send(404, {"error": "Not found"})
            state = m["state"] if m["active"] else "paused"
            color = {"up": "#168768", "down": "#bd465c", "paused": "#536179"}.get(state, "#536179")
            svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="176" height="24">'
                   '<rect width="176" height="24" rx="6" fill="#172337"/>'
                   '<rect x="117" width="59" height="24" rx="6" fill="' + color + '"/>'
                   '<text x="9" y="16" font-size="11" font-family="sans-serif" fill="#ffffff">GoreeCloud</text>'
                   '<text x="144" y="16" text-anchor="middle" font-size="11" font-family="sans-serif" fill="#ffffff">' +
                   xml_escape(state.upper()) + '</text></svg>')
            return self.send_text(200, svg, "image/svg+xml; charset=utf-8")
        if path == "/metrics":
            key = os.environ.get("GC_METRICS_TOKEN", "")
            provided = self.headers.get("Authorization", "")
            if len(key) < 24 or not hmac.compare_digest(provided, "Bearer " + key):
                return self.send(403, {"error": "Metrics unavailable or unauthorized"})
            with db() as con:
                rows = [dict(r) for r in con.execute("SELECT id,state,latency_ms FROM monitors")]
            lines = ["# TYPE goreecloud_monitor_up gauge"]
            for m in rows:
                number = 1 if m["state"] == "up" else 0
                lines.append('goreecloud_monitor_up{monitor_id="%s"} %s' % (m["id"], number))
            lines.append("# TYPE goreecloud_monitor_response_ms gauge")
            for m in rows:
                if m["latency_ms"] is not None:
                    lines.append('goreecloud_monitor_response_ms{monitor_id="%s"} %s' %
                                 (m["id"], m["latency_ms"]))
            return self.send_text(200, "\n".join(lines) + "\n", "text/plain; version=0.0.4; charset=utf-8")
        if path == "/api/me":
            if not self.protected():
                return
            return self.send(200, {"authenticated": True, "csrf": self.session()[1]})
        if not self.protected():
            return
        if path == "/api/monitors":
            return self.send(200, {"monitors": monitor_list()})
        if path == "/api/summary":
            with db() as con:
                total = con.execute("SELECT COUNT(*) FROM monitors").fetchone()[0]
                up = con.execute("SELECT COUNT(*) FROM monitors WHERE state='up' AND active=1").fetchone()[0]
                down = con.execute("SELECT COUNT(*) FROM monitors WHERE state='down' AND active=1").fetchone()[0]
                checks = con.execute("SELECT COUNT(*) FROM heartbeats").fetchone()[0]
            return self.send(200, {"total": total, "up": up, "down": down, "checks": checks,
                                   "maintenance": active_maintenance()})
        if path == "/api/history":
            with db() as con:
                rows = [dict(x) for x in con.execute("""SELECT h.time,h.state,h.latency_ms,h.detail,m.name
                   FROM heartbeats h JOIN monitors m ON m.id=h.monitor_id
                   ORDER BY h.id DESC LIMIT 80""")]
            return self.send(200, {"history": rows})
        if path == "/api/incidents":
            with db() as con:
                rows = [dict(r) for r in con.execute("SELECT * FROM incidents ORDER BY id DESC LIMIT 100")]
            return self.send(200, {"incidents": rows})
        if path == "/api/maintenance":
            with db() as con:
                rows = [dict(r) for r in con.execute("SELECT * FROM maintenance ORDER BY id DESC LIMIT 100")]
            return self.send(200, {"maintenance": rows})
        return self.send(404, {"error": "Not found"})

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        try:
            if path == "/api/login":
                ip = self.client_address[0]
                with LOGIN_LOCK:
                    recent = [x for x in LOGIN_ATTEMPTS.get(ip, []) if x > time.time()-300]
                    if len(recent) >= 8:
                        return self.send(429, {"error": "Too many attempts"})
                    recent.append(time.time())
                    LOGIN_ATTEMPTS[ip] = recent
                candidate = str(self.read_json().get("password", ""))
                if not hmac.compare_digest(candidate, self.server.admin_password):
                    return self.send(401, {"error": "Invalid credentials"})
                sid, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
                with SESSIONS_LOCK:
                    SESSIONS[sid] = (time.time() + SESSION_LIFETIME, csrf)
                with LOGIN_LOCK:
                    LOGIN_ATTEMPTS.pop(ip, None)
                return self.send(200, {"authenticated": True, "csrf": csrf},
                                 cookie="gc_session=" + sid + self.cookie_options())
            if path.startswith("/push/"):
                token = path.removeprefix("/push/")
                if len(token) < 30:
                    return self.send(404, {"error": "Unknown push monitor"})
                with db() as con:
                    row = con.execute("SELECT id FROM monitors WHERE token_hash=? AND active=1",
                                      (hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
                if row is None:
                    return self.send(404, {"error": "Unknown push monitor"})
                body = self.read_json()
                status = body.get("status", "up")
                if status not in ("up", "down"):
                    raise ValueError("Push status must be up or down")
                save_heartbeat(row["id"], status, None, "Push heartbeat")
                return self.send(200, {"ok": True})
            if not self.protected(write=True):
                return
            if path == "/api/logout":
                cookie = http.cookies.SimpleCookie()
                cookie.load(self.headers.get("Cookie", ""))
                sid = cookie.get("gc_session")
                if sid:
                    with SESSIONS_LOCK:
                        SESSIONS.pop(sid.value, None)
                return self.send(200, {"ok": True},
                                 cookie="gc_session=; Max-Age=0" + self.cookie_options())
            body = self.read_json()
            if path == "/api/monitors":
                parsed = validate_monitor(body)
                token = secrets.token_urlsafe(32) if parsed["kind"] == "push" else None
                digest = hashlib.sha256(token.encode()).hexdigest() if token else None
                with db() as con:
                    columns = ",".join(parsed.keys())
                    placeholders = ",".join(["?"] * len(parsed))
                    cur = con.execute("INSERT INTO monitors (" + columns + ",token_hash,created_at) VALUES (" +
                                      placeholders + ",?,?)", (*parsed.values(), digest, utcnow()))
                    mid = cur.lastrowid
                return self.send(201, {"id": mid, "push_token": token})
            if path == "/api/incidents":
                title = str(body.get("title", "")).strip()[:160]
                description = str(body.get("description", "")).strip()[:2000]
                if not title:
                    raise ValueError("Incident title required")
                with db() as con:
                    cur = con.execute("""INSERT INTO incidents(monitor_id,title,description,status,created_at,updated_at,public)
                       VALUES(NULL,?,?, 'investigating',?,?,?)""",
                       (title, description, utcnow(), utcnow(), int(body.get("public", False) is True)))
                return self.send(201, {"id": cur.lastrowid})
            if path == "/api/maintenance":
                title = str(body.get("title", "")).strip()[:160]
                starts = str(body.get("starts_at", ""))
                ends = str(body.get("ends_at", ""))
                if not title or len(title) > 160 or len(starts) > 40 or len(ends) > 40:
                    raise ValueError("Valid title and ISO UTC start/end are required")
                a, b = datetime.fromisoformat(starts), datetime.fromisoformat(ends)
                if a.tzinfo is None or b.tzinfo is None or b <= a:
                    raise ValueError("Maintenance times must have time zones and end after start")
                with db() as con:
                    cur = con.execute("INSERT INTO maintenance(title,description,starts_at,ends_at,created_at) VALUES(?,?,?,?,?)",
                                      (title, str(body.get("description", ""))[:2000],
                                       a.astimezone(timezone.utc).isoformat(timespec="seconds"),
                                       b.astimezone(timezone.utc).isoformat(timespec="seconds"), utcnow()))
                return self.send(201, {"id": cur.lastrowid})
            return self.send(404, {"error": "Not found"})
        except (ValueError, TypeError, OverflowError) as exc:
            return self.send(400, {"error": str(exc)})

    def do_PATCH(self):
        path = self.path.split("?", 1)[0]
        if not self.protected(write=True):
            return
        if path.startswith("/api/incidents/"):
            try:
                mid = int(path.rsplit("/", 1)[-1])
                body = self.read_json()
                if body.get("status") not in ("resolved", "investigating"):
                    raise ValueError("Incident status must be resolved or investigating")
                with db() as con:
                    cur = con.execute("UPDATE incidents SET status=?, updated_at=? WHERE id=?",
                                      (body["status"], utcnow(), mid))
                return self.send(200 if cur.rowcount else 404, {"ok": bool(cur.rowcount)})
            except (ValueError, TypeError) as exc:
                return self.send(400, {"error": str(exc)})
        if not path.startswith("/api/monitors/"):
            return self.send(404, {"error": "Not found"})
        try:
            mid = int(path.rsplit("/", 1)[-1])
            body = self.read_json()
            if type(body.get("active")) is not bool:
                raise ValueError("Expected boolean active state")
            with db() as con:
                cur = con.execute("UPDATE monitors SET active=? WHERE id=?", (int(body["active"]), mid))
            return self.send(200 if cur.rowcount else 404, {"ok": bool(cur.rowcount)})
        except (ValueError, TypeError) as exc:
            return self.send(400, {"error": str(exc)})

    def do_DELETE(self):
        path = self.path.split("?", 1)[0]
        if not self.protected(write=True):
            return
        if path.startswith("/api/maintenance/"):
            try:
                mid = int(path.rsplit("/", 1)[-1])
            except ValueError:
                return self.send(400, {"error": "Invalid maintenance identifier"})
            with db() as con:
                cur = con.execute("DELETE FROM maintenance WHERE id=?", (mid,))
            return self.send(200 if cur.rowcount else 404, {"ok": bool(cur.rowcount)})
        if not path.startswith("/api/monitors/"):
            return self.send(404, {"error": "Not found"})
        try:
            mid = int(path.rsplit("/", 1)[-1])
        except ValueError:
            return self.send(400, {"error": "Invalid monitor identifier"})
        with db() as con:
            cur = con.execute("DELETE FROM monitors WHERE id=?", (mid,))
        return self.send(200 if cur.rowcount else 404, {"ok": bool(cur.rowcount)})


def main():
    admin_password = password()
    if HOST not in ("127.0.0.1", "::1", "localhost") and not COOKIE_SECURE:
        raise RuntimeError("Non-loopback binding requires GC_COOKIE_SECURE=1 and TLS reverse proxy")
    initialize()
    server = http.server.ThreadingHTTPServer((HOST, PORT), Handler)
    server.admin_password = admin_password
    Scheduler().start()
    try:
        print(f"GoreeCloud Monitor listening on {HOST}:{PORT}", flush=True)
        server.serve_forever(poll_interval=0.5)
    finally:
        STOP.set()
        server.server_close()


if __name__ == "__main__":
    main()
