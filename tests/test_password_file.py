"""POSIX administrator password-file permissions and precedence tests.

Uses only temporary fixture files. Never reads or outputs real credentials.
"""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from monitor import server


@unittest.skipUnless(os.name == "posix", "POSIX permissions only")
class PasswordFileSecurityTests(unittest.TestCase):
    def test_owner_only_password_file_is_accepted_and_has_precedence(self):
        with tempfile.TemporaryDirectory() as temp:
            secret = Path(temp) / "password.txt"
            secret.write_text("fixture-password-long-enough\n", encoding="utf-8")
            secret.chmod(0o600)
            with patch.dict(os.environ, {
                "GC_ADMIN_PASSWORD_FILE": str(secret),
                "GC_ADMIN_PASSWORD": "different-ignored-credential",
            }):
                self.assertEqual(server.password(), "fixture-password-long-enough")
            secret.chmod(0o400)
            with patch.dict(os.environ, {"GC_ADMIN_PASSWORD_FILE": str(secret)}):
                self.assertEqual(server.password(), "fixture-password-long-enough")

    def test_group_or_world_readable_secret_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            secret = Path(temp) / "password.txt"
            secret.write_text("fixture-password-long-enough", encoding="utf-8")
            for unsafe in (0o640, 0o644, 0o666):
                with self.subTest(permissions=oct(unsafe)):
                    secret.chmod(unsafe)
                    with patch.dict(os.environ, {"GC_ADMIN_PASSWORD_FILE": str(secret)}):
                        with self.assertRaisesRegex(RuntimeError, "owner-only permissions"):
                            server.password()

    def test_password_file_must_be_regular_not_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.dict(os.environ, {"GC_ADMIN_PASSWORD_FILE": temp}):
                with self.assertRaisesRegex(RuntimeError, "regular file"):
                    server.password()

    def test_short_password_in_secure_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            secret = Path(temp) / "password.txt"
            secret.write_text("short", encoding="utf-8")
            secret.chmod(0o600)
            with patch.dict(os.environ, {"GC_ADMIN_PASSWORD_FILE": str(secret)}):
                with self.assertRaisesRegex(RuntimeError, "minimum 12 characters"):
                    server.password()


if __name__ == "__main__":
    unittest.main()
