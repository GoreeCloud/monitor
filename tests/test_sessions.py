"""Bounded in-memory operator session lifecycle acceptance tests."""
import http.client
import http.server
import json
import threading
import time
import unittest

from monitor import server


class SessionLifecycleTests(unittest.TestCase):
    def setUp(self):
        with server.SESSIONS_LOCK:
            self.previous = dict(server.SESSIONS)
            server.SESSIONS.clear()

    def tearDown(self):
        with server.SESSIONS_LOCK:
            server.SESSIONS.clear()
            server.SESSIONS.update(self.previous)

    def test_new_login_prunes_expired_session_records(self):
        now = time.time()
        with server.SESSIONS_LOCK:
            server.SESSIONS["old-expired"] = (now - 20, "old-csrf")
            server.SESSIONS["valid-session"] = (now + 300, "valid-csrf")
        session_id, csrf = server.create_session()
        self.assertTrue(session_id)
        self.assertTrue(csrf)
        with server.SESSIONS_LOCK:
            self.assertNotIn("old-expired", server.SESSIONS)
            self.assertIn("valid-session", server.SESSIONS)
            self.assertIn(session_id, server.SESSIONS)
            self.assertEqual(len(server.SESSIONS), 2)

    def test_session_cap_eviction_is_bounded_and_prioritizes_expiry(self):
        now = time.time()
        with server.SESSIONS_LOCK:
            for i in range(server.MAX_SESSIONS):
                server.SESSIONS["fixture-%03d" % i] = (now + i + 30, "csrf")
        fresh, csrf = server.create_session()
        self.assertTrue(csrf)
        with server.SESSIONS_LOCK:
            self.assertEqual(len(server.SESSIONS), server.MAX_SESSIONS)
            self.assertNotIn("fixture-000", server.SESSIONS)
            self.assertIn("fixture-001", server.SESSIONS)
            self.assertIn(fresh, server.SESSIONS)

    def test_preexisting_oversized_table_shrinks_on_login(self):
        now = time.time()
        with server.SESSIONS_LOCK:
            for i in range(server.MAX_SESSIONS + 35):
                server.SESSIONS["legacy-%03d" % i] = (now + i + 200, "csrf")
        fresh, csrf = server.create_session()
        with server.SESSIONS_LOCK:
            self.assertEqual(len(server.SESSIONS), server.MAX_SESSIONS)
            self.assertIn(fresh, server.SESSIONS)
            self.assertNotIn("legacy-000", server.SESSIONS)

    def test_expired_cookie_is_rejected_and_removed(self):
        with server.SESSIONS_LOCK:
            server.SESSIONS["expired-cookie"] = (time.time() - 10, "expired-csrf")
        http = http.server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        http.admin_password = "fixture-only-not-production-password"
        thread = threading.Thread(target=http.serve_forever, daemon=True)
        thread.start()
        try:
            connection = http.client.HTTPConnection("127.0.0.1", http.server_address[1], timeout=3)
            connection.request("GET", "/api/me", headers={
                "Cookie": "gc_session=expired-cookie"})
            response = connection.getresponse()
            payload = json.loads(response.read())
            self.assertEqual(response.status, 401)
            self.assertEqual(payload["error"], "Sign in required")
            connection.close()
            with server.SESSIONS_LOCK:
                self.assertNotIn("expired-cookie", server.SESSIONS)
        finally:
            http.shutdown()
            thread.join(timeout=5)
            http.server_close()

    def test_login_route_creates_capped_usable_session(self):
        now = time.time()
        with server.SESSIONS_LOCK:
            for i in range(server.MAX_SESSIONS):
                server.SESSIONS["fixture-%03d" % i] = (now + i + 15, "csrf")
        http = http.server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        http.admin_password = "fixture-only-not-production-password"
        thread = threading.Thread(target=http.serve_forever, daemon=True)
        thread.start()
        try:
            connection = http.client.HTTPConnection("127.0.0.1", http.server_address[1], timeout=3)
            connection.request("POST", "/api/login",
                body=json.dumps({"password": http.admin_password}),
                headers={"Content-Type": "application/json"})
            response = connection.getresponse()
            body = json.loads(response.read())
            cookie = response.getheader("Set-Cookie", "").split(";", 1)[0]
            self.assertEqual(response.status, 200)
            self.assertTrue(body["csrf"])
            self.assertTrue(cookie.startswith("gc_session="))
            connection.close()
            with server.SESSIONS_LOCK:
                self.assertEqual(len(server.SESSIONS), server.MAX_SESSIONS)
                self.assertNotIn("fixture-000", server.SESSIONS)
            session = http.client.HTTPConnection("127.0.0.1", http.server_address[1], timeout=3)
            session.request("GET", "/api/me", headers={"Cookie": cookie})
            authorized = session.getresponse()
            self.assertEqual(authorized.status, 200)
            self.assertEqual(json.loads(authorized.read())["csrf"], body["csrf"])
            session.close()
        finally:
            http.shutdown()
            thread.join(timeout=5)
            http.server_close()


if __name__ == "__main__":
    unittest.main()
