import os
import sqlite3
import tempfile
import threading
import http.client
import json
import http.server
import unittest
from unittest.mock import patch
from pathlib import Path

from monitor import server


class ValidationTests(unittest.TestCase):
    def test_reject_bad_kind(self):
        with self.assertRaises(ValueError):
            server.validate_monitor({"name": "one", "kind": "shell", "target": ""})

    def test_reject_invalid_timeouts(self):
        with self.assertRaises(ValueError):
            server.validate_monitor({"name": "one", "kind": "push", "timeout_seconds": 0})

    def test_accept_push(self):
        result = server.validate_monitor({"name": "Backup heartbeat", "kind": "push", "public": True})
        self.assertEqual(result["kind"], "push")
        self.assertEqual(result["target"], "")
        self.assertEqual(result["public"], 1)

    def test_private_ip_excluded(self):
        for ip in ("127.0.0.1", "10.1.2.3", "169.254.169.254", "::1"):
            self.assertFalse(server.valid_ip(ip))
        self.assertTrue(server.valid_ip("8.8.8.8"))

    def test_metadata_ip_always_blocked(self):
        self.assertFalse(server.valid_ip("169.254.169.254", allow_private=True))

    def test_http_invalid_userinfo(self):
        with self.assertRaises(ValueError):
            server.validate_monitor({"name": "x", "kind": "http", "target": "https://u:p@example.com/"})

    def test_tcp_target_validation(self):
        with self.assertRaises(ValueError):
            server.validate_monitor({"name": "x", "kind": "tcp", "target": "badport:NaN"})


class DatabaseTests(unittest.TestCase):
    def test_initialization_and_push_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            original_dir, original_db = server.DATA_DIR, server.DATABASE
            server.DATA_DIR = Path(tmp)
            server.DATABASE = Path(tmp) / "test.sqlite3"
            try:
                server.initialize()
                with server.db() as con:
                    cur = con.execute("""INSERT INTO monitors
                     (name,kind,target,interval_seconds,timeout_seconds,created_at)
                     VALUES('Backup','push','',60,8,?)""", (server.utcnow(),))
                    mid = cur.lastrowid
                server.save_heartbeat(mid, "up", None, "Push heartbeat")
                self.assertEqual(server.monitor_list()[0]["state"], "up")
                self.assertFalse(server.monitor_list(public=True))
                with server.db() as con:
                    self.assertEqual(con.execute("SELECT COUNT(*) FROM heartbeats").fetchone()[0], 1)
            finally:
                server.DATA_DIR, server.DATABASE = original_dir, original_db


if __name__ == "__main__":
    unittest.main()


class HttpIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_dir, self.old_db = server.DATA_DIR, server.DATABASE
        server.DATA_DIR = Path(self.tmp.name)
        server.DATABASE = Path(self.tmp.name) / "test.sqlite3"
        server.initialize()
        self.http = http.server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        self.http.admin_password = "strong-test-password-not-production"
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.http.shutdown()
        self.thread.join(timeout=5)
        self.http.server_close()
        server.DATA_DIR, server.DATABASE = self.old_dir, self.old_db
        self.tmp.cleanup()

    def call(self, method, path, data=None, cookie="", csrf=""):
        conn = http.client.HTTPConnection("127.0.0.1", self.http.server_address[1], timeout=3)
        headers = {"Content-Type":"application/json"}
        if cookie: headers["Cookie"] = cookie
        if csrf: headers["X-CSRF-Token"] = csrf
        body = json.dumps(data) if data is not None else None
        conn.request(method, path, body=body, headers=headers)
        response = conn.getresponse()
        payload = response.read()
        result = (response.status, payload, dict(response.getheaders()))
        conn.close()
        return result

    def login(self):
        status, payload, headers = self.call("POST", "/api/login", {"password":"strong-test-password-not-production"})
        self.assertEqual(status, 200)
        return headers["Set-Cookie"].split(";")[0], json.loads(payload)["csrf"]

    def test_readiness_requires_working_database(self):
        self.assertEqual(self.call("GET", "/healthz")[0], 200)
        status, data, _ = self.call("GET", "/readyz")
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(data)["ready"])
        with patch.object(server, "db", side_effect=sqlite3.OperationalError("unavailable")):
            status, data, _ = self.call("GET", "/readyz")
            self.assertEqual(status, 503)
            self.assertFalse(json.loads(data)["ready"])

    def test_authorization_and_csrf(self):
        self.assertEqual(self.call("GET", "/api/monitors")[0],401)
        self.assertEqual(self.call("POST", "/api/login", {"password":"wrong"})[0],401)
        cookie, csrf=self.login()
        self.assertEqual(self.call("POST","/api/monitors",{"name":"Job","kind":"push"},cookie)[0],403)
        self.assertEqual(self.call("POST","/api/monitors",{"name":"Job","kind":"push"},cookie,csrf)[0],201)

    def test_stats_public_only_and_sample_based(self):
        cookie, csrf = self.login()
        _, a, _ = self.call("POST", "/api/monitors", {"name": "Private", "kind": "push"}, cookie, csrf)
        _, b, _ = self.call("POST", "/api/monitors",
                             {"name": "Public", "kind": "push", "public": True}, cookie, csrf)
        private, public_monitor = json.loads(a), json.loads(b)
        self.assertEqual(self.call("GET", "/api/stats")[0], 401)
        for status in ("up", "up", "down", "down"):
            self.assertEqual(self.call("POST", "/push/" + public_monitor["push_token"],
                                       {"status": status})[0], 200)
        self.assertEqual(self.call("POST", "/push/" + private["push_token"],
                                   {"status": "up"})[0], 200)
        public_stats = json.loads(self.call("GET", "/api/public")[1])["stats"]
        self.assertNotIn(str(private["id"]), public_stats)
        sample = public_stats[str(public_monitor["id"])]
        self.assertEqual(sample["checks"], 4)
        self.assertEqual(sample["successful"], 2)
        self.assertEqual(sample["pass_rate"], 50.0)
        internal = json.loads(self.call("GET", "/api/stats", cookie=cookie)[1])["stats"]
        self.assertIn(str(private["id"]), internal)

    def test_empty_stats_report_no_rate(self):
        cookie, csrf = self.login()
        _, body, _ = self.call("POST", "/api/monitors",
                               {"name": "No checks", "kind": "push"}, cookie, csrf)
        key = str(json.loads(body)["id"])
        stats = json.loads(self.call("GET", "/api/stats", cookie=cookie)[1])["stats"]
        self.assertEqual(stats[key]["checks"], 0)
        self.assertIsNone(stats[key]["pass_rate"])

    def test_public_privacy_and_badge(self):
        cookie,csrf=self.login()
        _,body,_=self.call("POST","/api/monitors",{"name":"Private","kind":"push"},cookie,csrf)
        private_id=json.loads(body)["id"]
        self.assertEqual(json.loads(self.call("GET","/api/public")[1])["monitors"],[])
        self.assertEqual(self.call("GET","/badge/%d.svg"%private_id)[0],404)
        _,body,_=self.call("POST","/api/monitors",{"name":"Public","kind":"push","public":True},cookie,csrf)
        public_id=json.loads(body)["id"]
        self.assertEqual(len(json.loads(self.call("GET","/api/public")[1])["monitors"]),1)
        status,body,headers=self.call("GET","/badge/%d.svg"%public_id)
        self.assertEqual(status,200)
        self.assertIn(b"<svg",body)
        self.assertTrue(headers["Content-Type"].startswith("image/svg+xml"))

    def test_public_rss_escapes_markup(self):
        cookie,csrf=self.login()
        self.call("POST","/api/incidents",{"title":"Alert <script>","description":"a & b","public":True},cookie,csrf)
        status,content,_=self.call("GET","/status.rss")
        self.assertEqual(status,200)
        self.assertIn(b"&lt;script&gt;",content)
        self.assertIn(b"a &amp; b",content)
        self.assertNotIn(b"<script>",content)

    def test_metrics_denied_by_default(self):
        self.assertEqual(self.call("GET","/metrics")[0],403)

    def test_incident_resolution(self):
        cookie,csrf=self.login()
        _,data,_=self.call("POST","/api/incidents",{"title":"Investigating"},cookie,csrf)
        id=json.loads(data)["id"]
        status,_,_=self.call("PATCH","/api/incidents/%d"%id,{"status":"resolved"},cookie,csrf)
        self.assertEqual(status,200)
        incidents=json.loads(self.call("GET","/api/incidents",cookie=cookie)[1])["incidents"]
        self.assertEqual(incidents[0]["status"],"resolved")

    def test_notify_transition_only(self):
        cookie, csrf = self.login()
        _, body, _ = self.call("POST", "/api/monitors", {"name":"Backup job","kind":"push"},cookie,csrf)
        token=json.loads(body)["push_token"]
        with patch.object(server.NOTIFY_POOL,"submit") as submit:
            self.call("POST","/push/"+token,{"status":"down"})
            self.assertEqual(submit.call_count,0)
            self.call("POST","/push/"+token,{"status":"down"})
            self.assertEqual(submit.call_count,1)
            self.call("POST","/push/"+token,{"status":"up"})
            self.assertEqual(submit.call_count,2)

    def test_maintenance_is_private_by_default(self):
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        start = (now + timedelta(hours=1)).isoformat()
        end = (now + timedelta(hours=2)).isoformat()
        cookie, csrf = self.login()
        private = {"title": "Private infrastructure work", "description": "Private host names",
                   "starts_at": start, "ends_at": end}
        status, _, _ = self.call("POST", "/api/maintenance", private, cookie, csrf)
        self.assertEqual(status, 201)
        public = json.loads(self.call("GET", "/api/public")[1])
        self.assertEqual(public["maintenance"], [])
        published = {**private, "title": "Public maintenance", "description": "Approved public details", "public": True}
        self.assertEqual(self.call("POST", "/api/maintenance", published, cookie, csrf)[0], 201)
        public = json.loads(self.call("GET", "/api/public")[1])
        self.assertEqual([item["title"] for item in public["maintenance"]], ["Public maintenance"])
        self.assertNotIn(b"Private host names", self.call("GET", "/api/public")[1])

    def test_schema_migrates_maintenance_to_private(self):
        with server.db() as con:
            con.execute("DROP TABLE maintenance")
            con.execute("""CREATE TABLE maintenance (
                id INTEGER PRIMARY KEY, title TEXT NOT NULL,
                description TEXT NOT NULL, starts_at TEXT NOT NULL,
                ends_at TEXT NOT NULL, created_at TEXT NOT NULL)""")
            con.execute("""INSERT INTO maintenance
                (title,description,starts_at,ends_at,created_at)
                VALUES('Legacy maintenance','Sensitive notes','2099-01-01T00:00:00+00:00',
                       '2099-01-01T01:00:00+00:00','2026-11-04T00:00:00+00:00')""")
        server.initialize()
        with server.db() as con:
            row = con.execute("SELECT title,description,public FROM maintenance").fetchone()
        self.assertEqual(row["title"], "Legacy maintenance")
        self.assertEqual(row["description"], "Sensitive notes")
        self.assertEqual(row["public"], 0)
        self.assertEqual(json.loads(self.call("GET", "/api/public")[1])["maintenance"], [])

    def test_push_is_rate_limited(self):
        cookie, csrf = self.login()
        _, body, _ = self.call("POST", "/api/monitors",
                               {"name": "Rate-limited job", "kind": "push"}, cookie, csrf)
        monitor = json.loads(body)
        url = "/push/" + monitor["push_token"]
        with patch.object(server, "PUSH_RATE_LIMIT", 2):
            self.assertEqual(self.call("POST", url, {"status": "up"})[0], 200)
            self.assertEqual(self.call("POST", url, {"status": "up"})[0], 200)
            self.assertEqual(self.call("POST", url, {"status": "up"})[0], 429)
        with server.db() as con:
            result = con.execute("SELECT COUNT(*) FROM heartbeats WHERE monitor_id=?",
                                 (monitor["id"],)).fetchone()[0]
        self.assertEqual(result, 2)

    def test_pinned_http_connection(self):
        # The chosen target is a hostname absent from DNS; the socket must use
        # the explicitly validated address supplied by the policy layer.
        with patch.object(server,"addresses") as resolve:
            resolve.return_value=[(2,1,6,"",("127.0.0.1",self.http.server_address[1]))]
            server.pinned_http_probe("http://example.invalid:%d/healthz"%self.http.server_address[1],
                                     3,200,'"ok":true')
            self.assertEqual(resolve.call_count,1)
