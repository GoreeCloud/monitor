"""Regression tests for explicit HTTP port handling.

Invalid destinations must be rejected before DNS lookups or outbound network I/O.
"""
import unittest
from unittest.mock import patch

from monitor import server


class HttpPortValidationTests(unittest.TestCase):
    def test_explicit_zero_port_rejected_before_dns_for_both_schemes(self):
        for scheme in ("http", "https"):
            with self.subTest(scheme=scheme), patch.object(server, "addresses") as resolve:
                with self.assertRaisesRegex(ValueError, "Invalid URL port"):
                    server.validate_monitor({
                        "name": "Invalid explicit port", "kind": "http",
                        "target": scheme + "://example.test:0/health"
                    })
                resolve.assert_not_called()

    def test_valid_and_omitted_port_still_resolve_correctly(self):
        for scheme, default in (("http", 80), ("https", 443)):
            for suffix in ("", ":" + str(default)):
                with self.subTest(scheme=scheme, suffix=suffix), \
                        patch.object(server, "addresses") as resolve:
                    result = server.validate_monitor({
                        "name": "Valid HTTP target", "kind": "http",
                        "target": scheme + "://example.test" + suffix + "/health"
                    })
                    self.assertEqual(result["kind"], "http")
                    resolve.assert_called_once_with("example.test", default, False)

    def test_direct_probe_rejects_zero_port_without_network_access(self):
        for scheme in ("http", "https"):
            with self.subTest(scheme=scheme), patch.object(server, "addresses") as resolve:
                with self.assertRaisesRegex(ValueError, "Invalid URL port"):
                    server.pinned_http_probe(
                        scheme + "://example.test:0/health", 3, 200, "")
                resolve.assert_not_called()


if __name__ == "__main__":
    unittest.main()
