"""Bounded and concurrency-safe login source throttling regressions.

All HTTP interactions use a disposable loopback listener and fixture password.
No production credentials, remote hosts or external networking.
"""
import http.client
import http.server
import json
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from monitor import server


class BoundedLoginSourceTests(unittest.TestCase):
    def setUp(self):
        with server.LOGIN_LOCK:
            self.previous = {ip: list(stamps)
                             for ip, stamps in server.LOGIN_ATTEMPTS.items()}
            server.LOGIN_ATTEMPTS.clear()

    def tearDown(self):
        with server.LOGIN_LOCK:
            server.LOGIN_ATTEMPTS.clear()
            server.LOGIN_ATTEMPTS.update(self.previous)

    def test_attempt_window_does_not_reset_after_rejection(self):
        for n in range(server.LOGIN_ATTEMPT_LIMIT):
            self.assertTrue(server.record_login_attempt("192.0.2.5", now=100+n))
        self.assertFalse(server.record_login_attempt("192.0.2.5", now=108))
        self.assertEqual(len(server.LOGIN_ATTEMPTS["192.0.2.5"]),
                         server.LOGIN_ATTEMPT_LIMIT)
        self.assertTrue(server.record_login_attempt(
            "192.0.2.5", now=108 + server.LOGIN_WINDOW_SECONDS))
        self.assertEqual(len(server.LOGIN_ATTEMPTS["192.0.2.5"]), 1)

    def test_source_capacity_denies_new_ip_but_keeps_existing_budget(self):
        with patch.object(server, "MAX_LOGIN_SOURCES", 2):
            self.assertTrue(server.record_login_attempt("198.51.100.1", now=100))
            self.assertTrue(server.record_login_attempt("198.51.100.2", now=100))
            self.assertFalse(server.record_login_attempt("203.0.113.9", now=101))
            self.assertTrue(server.record_login_attempt("198.51.100.1", now=101))
            self.assertEqual(len(server.LOGIN_ATTEMPTS), 2)
            self.assertEqual(len(server.LOGIN_ATTEMPTS["198.51.100.1"]), 2)
            self.assertNotIn("203.0.113.9", server.LOGIN_ATTEMPTS)

    def test_expired_source_buckets_are_pruned_at_capacity(self):
        with patch.object(server, "MAX_LOGIN_SOURCES", 2):
            self.assertTrue(server.record_login_attempt("old-one", now=10))
            self.assertTrue(server.record_login_attempt("old-two", now=20))
            self.assertTrue(server.record_login_attempt("new-source", now=401))
            self.assertEqual(set(server.LOGIN_ATTEMPTS), {"new-source"})

    def test_concurrent_unique_addresses_cannot_exceed_limit(self):
        with patch.object(server, "MAX_LOGIN_SOURCES", 40):
            with ThreadPoolExecutor(max_workers=16) as pool:
                accepted = list(pool.map(
                    lambda n: server.record_login_attempt(
                        "198.51.100." + str(n), now=100),
                    range(240)))
            self.assertEqual(sum(accepted), 40)
            with server.LOGIN_LOCK:
                self.assertEqual(len(server.LOGIN_ATTEMPTS), 40)
                self.assertTrue(all(len(v) == 1
                                    for v in server.LOGIN_ATTEMPTS.values()))

    def test_full_table_rejects_http_login_even_with_spoofed_forwarded_ip(self):
        with patch.object(server, "MAX_LOGIN_SOURCES", 1):
            self.assertTrue(server.record_login_attempt(
                "198.51.100.23", now=time.monotonic()))
            listener = http.server.ThreadingHTTPServer(
                ("127.0.0.1", 0), server.Handler)
            listener.admin_password = "fixture-only-operator-password"
            thread = threading.Thread(target=listener.serve_forever, daemon=True)
            thread.start()
            try:
                conn = http.client.HTTPConnection(
                    "127.0.0.1", listener.server_address[1], timeout=3)
                conn.request("POST", "/api/login",
                             body=json.dumps({"password": listener.admin_password}),
                             headers={"Content-Type": "application/json",
                                      "X-Forwarded-For": "198.51.100.23"})
                response = conn.getresponse()
                self.assertEqual(response.status, 429)
                self.assertEqual(json.loads(response.read())["error"],
                                 "Too many attempts")
                conn.close()
                self.assertEqual(list(server.LOGIN_ATTEMPTS), ["198.51.100.23"])
            finally:
                listener.shutdown()
                thread.join(timeout=5)
                listener.server_close()

    def test_expired_peer_budget_allows_real_http_login(self):
        with patch.object(server, "MAX_LOGIN_SOURCES", 1):
            with server.LOGIN_LOCK:
                server.LOGIN_ATTEMPTS["127.0.0.1"] = [
                    time.monotonic() - server.LOGIN_WINDOW_SECONDS - 1]
            listener = http.server.ThreadingHTTPServer(
                ("127.0.0.1", 0), server.Handler)
            listener.admin_password = "fixture-only-operator-password"
            thread = threading.Thread(target=listener.serve_forever, daemon=True)
            thread.start()
            try:
                conn = http.client.HTTPConnection(
                    "127.0.0.1", listener.server_address[1], timeout=3)
                conn.request("POST", "/api/login",
                             body=json.dumps({"password": listener.admin_password}),
                             headers={"Content-Type": "application/json"})
                response = conn.getresponse()
                body = json.loads(response.read())
                self.assertEqual(response.status, 200)
                self.assertTrue(body["csrf"])
                self.assertIn("HttpOnly", response.getheader("Set-Cookie"))
                conn.close()
            finally:
                listener.shutdown()
                thread.join(timeout=5)
                listener.server_close()


if __name__ == "__main__":
    unittest.main()
