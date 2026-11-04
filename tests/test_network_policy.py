"""Network-policy regressions verified on Python 3.12 and 3.13.

No live DNS, outbound sockets or production hosts are used.
"""
import socket
import unittest
from unittest.mock import patch

from monitor import server


class AddressPolicyRegressionTests(unittest.TestCase):
    def test_loopback_and_metadata_denied_with_private_opt_in(self):
        for address in ("127.0.0.1", "169.254.169.254", "::1",
                        "::ffff:127.0.0.1", "::ffff:169.254.169.254"):
            for allow_private in (False, True):
                with self.subTest(address=address, allow_private=allow_private):
                    self.assertFalse(server.valid_ip(address, allow_private))

    def test_link_local_multicast_and_unspecified_always_denied(self):
        for address in ("0.0.0.0", "224.0.0.1", "fe80::1%eth0", "ff02::1", "::"):
            for allow_private in (False, True):
                with self.subTest(address=address, allow_private=allow_private):
                    self.assertFalse(server.valid_ip(address, allow_private))

    def test_native_private_addresses_require_explicit_opt_in(self):
        for address in ("10.23.1.8", "172.16.1.3", "192.168.1.10"):
            with self.subTest(address=address):
                self.assertFalse(server.valid_ip(address, False))
                self.assertTrue(server.valid_ip(address, True))

    def test_mapped_ipv6_obeys_embedded_ipv4_policy(self):
        examples = (
            ("::ffff:8.8.8.8", False, True),
            ("::ffff:10.23.1.8", False, False),
            ("::ffff:10.23.1.8", True, True),
            ("::ffff:127.0.0.1", True, False),
            ("::ffff:169.254.169.254", True, False),
            ("::ffff:224.0.0.1", True, False),
        )
        for address, allow_private, permitted in examples:
            with self.subTest(address=address, allow_private=allow_private):
                self.assertEqual(server.valid_ip(address, allow_private), permitted)

    def test_mixed_dns_answers_are_rejected_before_connect(self):
        answers = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443)),
        ]
        with patch.object(server.socket, "getaddrinfo", return_value=answers):
            with self.assertRaisesRegex(ValueError, "network policy"):
                server.addresses("mixed.example.test", 443, allow_private=False)

    def test_dns_failure_does_not_expose_resolver_detail(self):
        with patch.object(server.socket, "getaddrinfo",
                          side_effect=socket.gaierror("internal resolver detail")):
            with self.assertRaises(ValueError) as raised:
                server.addresses("missing.example.test", 443)
            self.assertEqual(str(raised.exception), "Hostname could not be resolved")
            self.assertNotIn("internal resolver", str(raised.exception))

    def test_allow_private_does_not_override_mixed_answer_denial(self):
        answers = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.1.2.3", 443)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("169.254.169.254", 443)),
        ]
        with patch.object(server.socket, "getaddrinfo", return_value=answers):
            with self.assertRaisesRegex(ValueError, "network policy"):
                server.addresses("private-mixed.example.test", 443, allow_private=True)


if __name__ == "__main__":
    unittest.main()
