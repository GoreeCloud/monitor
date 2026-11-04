"""Operational backup acceptance tests."""
import os
from pathlib import Path
import sqlite3
import stat
import tempfile
import unittest

from monitor import backup, server


class BackupTests(unittest.TestCase):
    def test_snapshot_integrity_private_mode_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            prior_dir, prior_db = server.DATA_DIR, server.DATABASE
            try:
                server.DATA_DIR = Path(td) / "data"
                server.DATABASE = server.DATA_DIR / "monitor.sqlite3"
                server.initialize()
                with server.db() as conn:
                    conn.execute("""INSERT INTO monitors
                        (name,kind,target,interval_seconds,timeout_seconds,created_at)
                        VALUES('Backup check','push','',60,8,?)""", (server.utcnow(),))
                    mid = conn.execute("SELECT id FROM monitors").fetchone()[0]
                server.save_heartbeat(mid, "up", None, "OK")
                destination = Path(td) / "snapshot.sqlite3"
                digest = backup.create_backup(destination)
                self.assertEqual(len(digest), 64)
                self.assertEqual(stat.S_IMODE(destination.stat().st_mode), 0o600)
                with sqlite3.connect(destination) as copy:
                    self.assertEqual(copy.execute("PRAGMA integrity_check").fetchone()[0], "ok")
                    self.assertEqual(copy.execute("SELECT COUNT(*) FROM monitors").fetchone()[0], 1)
                    self.assertEqual(copy.execute("SELECT COUNT(*) FROM heartbeats").fetchone()[0], 1)
                with self.assertRaises(FileExistsError):
                    backup.create_backup(destination)
            finally:
                server.DATA_DIR, server.DATABASE = prior_dir, prior_db

    def test_missing_source_is_not_created(self):
        with tempfile.TemporaryDirectory() as td:
            prior = server.DATABASE
            try:
                server.DATABASE = Path(td) / "missing.sqlite3"
                with self.assertRaises(FileNotFoundError):
                    backup.create_backup(Path(td) / "backup.sqlite3")
                self.assertFalse(server.DATABASE.exists())
            finally:
                server.DATABASE = prior


if __name__ == "__main__":
    unittest.main()
