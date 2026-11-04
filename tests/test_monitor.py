import os
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

    def test_authorization_and_csrf(self):
        self.assertEqual(self.call("GET", "/api/monitors")[0],401)
        self.assertEqual(self.call("POST", "/api/login", {"password":"wrong"})[0],401)
        cookie, csrf=self.login()
        self.assertEqual(self.call("POST","/api/monitors",{"name":"Job","kind":"push"},cookie)[0],403)
        self.assertEqual(self.call("POST","/api/monitors",{"name":"Job","kind":"push"},cookie,csrf)[0],201)

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

    def test_pinned_http_connection(self):
        # The chosen target is a hostname absent from DNS; the socket must use
        # the explicitly validated address supplied by the policy layer.
        with patch.object(server,"addresses") as resolve:
            resolve.return_value=[(2,1,6,"",("127.0.0.1",self.http.server_address[1]))]
            server.pinned_http_probe("http://example.invalid:%d/healthz"%self.http.server_address[1],
                                     3,200,'"ok":true')
            self.assertEqual(resolve.call_count,1)
