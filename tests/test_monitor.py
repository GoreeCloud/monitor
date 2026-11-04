import os
import tempfile
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
