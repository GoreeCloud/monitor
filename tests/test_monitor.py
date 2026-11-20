import http.client
import json
import socket
import tempfile
import threading
import unittest
from unittest.mock import patch
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "service"))
from monitor import MonitorService, connect, handler_factory, parse_monitor, probe


class LocalTarget(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, *args):
        pass


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.service = MonitorService(Path(self.temp.name) / "monitor.db",
                                      "a" * 48, allow_private=True)

    def tearDown(self):
        self.service.close()
        self.temp.cleanup()

    def test_reject_unsafe_input(self):
        invalid = [
            {"name": "", "target": "https://example.com"},
            {"name": "bad", "target": "file:///etc/passwd"},
            {"name": "bad", "target": "https://u:p@example.com"},
            {"name": "bad", "target": "https://example.com", "interval_s": 1},
            {"name": "bad", "target": "tcp://example.com"},
            {"name": "bad", "target": "https://example.com", "public": "yes"},
        ]
        for config in invalid:
            with self.subTest(config=config), self.assertRaises(ValueError):
                parse_monitor(config)

    def test_public_is_opt_in_and_private_targets_are_hidden(self):
        a = self.service.create({"name": "private", "target": "https://example.com"})
        b = self.service.create({"name": "public", "target": "https://example.org", "public": True})
        self.assertEqual(len(self.service.list_monitors()), 2)
        status = self.service.status()
        self.assertEqual(status["summary"]["total"], 1)
        self.assertEqual(status["monitors"][0]["id"], b)
        self.assertNotIn("target", status["monitors"][0])
        self.assertNotIn("example.com", json.dumps(status))
        self.assertTrue(a)

    def test_http_probe_and_incident_recovery(self):
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), LocalTarget)
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        try:
            url = "http://127.0.0.1:%s/ready" % httpd.server_port
            mid = self.service.create({"name": "local", "target": url, "public": True})
            first = self.service.check(mid)
            self.assertEqual(first["state"], "up")
            self.assertEqual(len(self.service.history(mid)), 1)
            httpd.shutdown()
            httpd.server_close()
            second = self.service.check(mid)
            self.assertEqual(second["state"], "down")
            self.assertEqual(len(self.service.status()["incidents"]), 1)
            self.assertEqual(len(self.service.history(mid)), 2)
        finally:
            httpd.server_close()

    def test_incident_transitions_are_deduplicated_and_resolved(self):
        mid = self.service.create({"name": "Webhook", "target": "https://example.org", "public": True})
        with patch("monitor.probe", side_effect=[
            (False, 10, "HTTP 500"),
            (False, 12, "HTTP 500"),
            (True, 11, "HTTP 200"),
        ]):
            self.assertEqual(self.service.check(mid)["state"], "down")
            self.assertEqual(self.service.check(mid)["state"], "down")
            self.assertEqual(len(self.service.status()["incidents"]), 1)
            self.assertEqual(self.service.check(mid)["state"], "up")
        self.assertEqual(self.service.status()["incidents"], [])
        with connect(self.service.path) as db:
            rows = list(db.execute("SELECT started_at,resolved_at FROM incidents WHERE monitor_id=?", (mid,)))
        self.assertEqual(len(rows), 1)
        self.assertIsNotNone(rows[0]["resolved_at"])

    def test_private_probe_blocked_without_opt_in(self):
        m = parse_monitor({"name": "loopback", "target": "tcp://127.0.0.1:1234"})
        ok, _, detail = probe(m, allow_private=False)
        self.assertFalse(ok)
        self.assertIn("blocked", detail)

    def test_authenticated_api_and_public_read(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler_factory(self.service))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            def request(method, path, body=None, token=None):
                c = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
                headers = {"Content-Type": "application/json"}
                if token:
                    headers["Authorization"] = "Bearer " + token
                c.request(method, path, body=json.dumps(body) if body else None, headers=headers)
                response = c.getresponse()
                status, payload = response.status, response.read()
                c.close()
                return status, json.loads(payload)
            self.assertEqual(request("GET", "/api/v1/status")[0], 200)
            self.assertEqual(request("GET", "/api/v1/monitors")[0], 401)
            self.assertEqual(request("POST", "/api/v1/monitors",
                            {"name": "No auth", "target": "https://example.org"})[0], 401)
            code, created = request("POST", "/api/v1/monitors",
                                    {"name": "Public", "target": "https://example.org",
                                     "public": True}, "a" * 48)
            self.assertEqual(code, 201)
            self.assertEqual(request("GET", "/api/v1/status")[1]["summary"]["total"], 1)
            self.assertEqual(request("DELETE", "/api/v1/monitors/" + created["id"], token="a" * 48)[0], 200)
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
