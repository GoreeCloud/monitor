"""Loopback-only TLS reverse-proxy acceptance for GoreeCloud Monitor.

No external network connections, production credentials, or deployed proxy.
A disposable self-signed test CA is generated at runtime and never committed.
"""
import http.client
import http.server
import json
import os
from pathlib import Path
import shutil
import ssl
import subprocess
import tempfile
import threading
import unittest

from monitor import server


class LocalTLSGateway(http.server.BaseHTTPRequestHandler):
    """Tiny isolated TLS terminator; not production proxy configuration."""

    def log_message(self, fmt, *args):
        return  # Keep fixture credentials and HTTP paths out of logs.

    def do_GET(self):
        self.relay()

    def do_POST(self):
        self.relay()

    def do_PATCH(self):
        self.relay()

    def relay(self):
        size = int(self.headers.get("Content-Length", "0"))
        if size < 0 or size > 16384:
            self.send_error(413)
            return
        body = self.rfile.read(size) if size else None
        headers = {
            "Host": "localhost",
            "X-Forwarded-Proto": "https",
            # Untrusted forwarded identity must never grant authentication.
            "X-Forwarded-For": "198.51.100.123",
        }
        for name in ("Cookie", "Content-Type", "X-CSRF-Token"):
            if name in self.headers:
                headers[name] = self.headers[name]
        origin = http.client.HTTPConnection(
            "127.0.0.1", self.server.origin_port, timeout=5)
        try:
            origin.request(self.command, self.path, body=body, headers=headers)
            response = origin.getresponse()
            payload = response.read()
            self.send_response(response.status)
            for name, value in response.getheaders():
                if name.lower() not in (
                    "server", "date", "connection", "transfer-encoding",
                    "content-length", "strict-transport-security"
                ):
                    self.send_header(name, value)
            self.send_header("Content-Length", str(len(payload)))
            # This is a demonstration of an edge-only header; the application
            # doesn't add or enforce HSTS for an actual deployment.
            self.send_header("Strict-Transport-Security", "max-age=86400")
            self.end_headers()
            self.wfile.write(payload)
        finally:
            origin.close()


class LocalTLSProxyAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if shutil.which("openssl") is None:
            raise RuntimeError("openssl is required for local TLS acceptance")
        cls.work = tempfile.TemporaryDirectory(prefix="gc-monitor-tls-")
        root = Path(cls.work.name)
        root.chmod(0o700)
        cert = root / "fixture-localhost.pem"
        key = root / "fixture-key.pem"
        subprocess.run(
            [
                "openssl", "req", "-x509", "-newkey", "rsa:2048",
                "-sha256", "-nodes", "-days", "1", "-subj", "/CN=localhost",
                "-addext", "subjectAltName=DNS:localhost",
                "-keyout", str(key), "-out", str(cert)
            ],
            check=True, timeout=20, stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        os.chmod(key, 0o600)
        cls.previous = (server.DATA_DIR, server.DATABASE, server.COOKIE_SECURE)
        server.DATA_DIR = root / "database"
        server.DATABASE = server.DATA_DIR / "monitor.sqlite3"
        server.COOKIE_SECURE = True
        server.initialize()

        cls.origin = http.server.ThreadingHTTPServer(
            ("127.0.0.1", 0), server.Handler)
        cls.origin.admin_password = "fixture-only-reverse-proxy-test-password"
        cls.origin_thread = threading.Thread(
            target=cls.origin.serve_forever, daemon=True)
        cls.origin_thread.start()

        cls.gateway = http.server.ThreadingHTTPServer(
            ("127.0.0.1", 0), LocalTLSGateway)
        cls.gateway.origin_port = cls.origin.server_address[1]
        tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        tls.load_cert_chain(certfile=str(cert), keyfile=str(key))
        cls.gateway.socket = tls.wrap_socket(
            cls.gateway.socket, server_side=True)
        cls.gateway_thread = threading.Thread(
            target=cls.gateway.serve_forever, daemon=True)
        cls.gateway_thread.start()
        cls.verified_context = ssl.create_default_context(cafile=str(cert))

    @classmethod
    def tearDownClass(cls):
        for instance, thread in (
            (cls.gateway, cls.gateway_thread),
            (cls.origin, cls.origin_thread)
        ):
            instance.shutdown()
            thread.join(timeout=5)
            instance.server_close()
        server.DATA_DIR, server.DATABASE, server.COOKIE_SECURE = cls.previous
        cls.work.cleanup()

    def setUp(self):
        with server.SESSIONS_LOCK:
            server.SESSIONS.clear()
        with server.LOGIN_LOCK:
            server.LOGIN_ATTEMPTS.clear()

    def https(self, method, path, body=None, cookie="", csrf="", headers=None):
        connection = http.client.HTTPSConnection(
            "localhost", self.gateway.server_address[1], timeout=5,
            context=self.verified_context)
        values = dict(headers or {})
        if body is not None:
            values["Content-Type"] = "application/json"
        if cookie:
            values["Cookie"] = cookie
        if csrf:
            values["X-CSRF-Token"] = csrf
        connection.request(method, path,
                           body=json.dumps(body) if body is not None else None,
                           headers=values)
        result = connection.getresponse()
        raw = result.read()
        response_headers = dict(result.getheaders())
        status = result.status
        connection.close()
        if "application/json" in response_headers.get("Content-Type", ""):
            return status, json.loads(raw), response_headers
        return status, raw, response_headers

    def test_https_certificate_trust_is_explicit(self):
        # A self-signed fixture cert fails system trust, but succeeds when
        # precisely that disposable CA certificate is explicitly trusted.
        untrusted = http.client.HTTPSConnection(
            "localhost", self.gateway.server_address[1], timeout=5,
            context=ssl.create_default_context())
        try:
            with self.assertRaises(ssl.SSLCertVerificationError):
                untrusted.request("GET", "/readyz")
        finally:
            untrusted.close()
        status, body, _ = self.https("GET", "/readyz")
        self.assertEqual(status, 200)
        self.assertTrue(body["ready"])

    def test_proxy_headers_static_csp_and_edge_hsts(self):
        self.assertEqual(self.origin.server_address[0], "127.0.0.1")
        self.assertEqual(self.gateway.server_address[0], "127.0.0.1")
        status, document, headers = self.https("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b"GoreeCloud Monitor", document)
        self.assertIn("frame-ancestors 'none'",
                      headers["Content-Security-Policy"])
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["Strict-Transport-Security"], "max-age=86400")

    def test_secure_cookie_csrf_private_visibility_and_logout(self):
        status, body, _ = self.https("GET", "/api/monitors")
        self.assertEqual(status, 401)
        self.assertEqual(body["error"], "Sign in required")
        status, body, headers = self.https("POST", "/api/login", {
            "password": self.origin.admin_password})
        self.assertEqual(status, 200)
        token = body["csrf"]
        set_cookie = headers["Set-Cookie"]
        self.assertTrue(set_cookie.startswith("gc_session="))
        for flag in ("HttpOnly", "SameSite=Strict", "Secure"):
            self.assertIn(flag, set_cookie)
        cookie = set_cookie.split(";", 1)[0]
        private = {"name": "TLS fixture private service", "kind": "push",
                   "public": False}
        status, _, _ = self.https("POST", "/api/monitors", private,
                                  cookie=cookie)
        self.assertEqual(status, 403, "write must require session CSRF")
        status, created, _ = self.https("POST", "/api/monitors", private,
                                         cookie=cookie, csrf=token)
        self.assertEqual(status, 201)
        self.assertGreater(created["id"], 0)
        status, inventory, _ = self.https("GET", "/api/monitors",
                                          cookie=cookie)
        self.assertEqual(status, 200)
        self.assertIn(created["id"], [
            item["id"] for item in inventory["monitors"]])
        status, public, _ = self.https("GET", "/api/public")
        self.assertEqual(status, 200)
        self.assertNotIn(created["id"], [
            item["id"] for item in public["monitors"]])
        self.assertNotIn("push_token", json.dumps(public))
        status, _, headers = self.https("POST", "/api/logout", cookie=cookie,
                                         csrf=token)
        self.assertEqual(status, 200)
        self.assertIn("Max-Age=0", headers["Set-Cookie"])
        self.assertEqual(self.https("GET", "/api/me", cookie=cookie)[0], 401)

    def test_forwarded_identity_headers_do_not_authorize_admin(self):
        status, _, _ = self.https("GET", "/api/monitors", headers={
            "X-Forwarded-For": "127.0.0.1",
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Host": "localhost",
        })
        self.assertEqual(status, 401)
        status, _, _ = self.https("PATCH", "/api/monitors/9999", headers={
            "X-Forwarded-For": "127.0.0.1"
        })
        self.assertEqual(status, 401)


if __name__ == "__main__":
    unittest.main()
