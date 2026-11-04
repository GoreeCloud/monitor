"""Operational backup acceptance tests."""
import os
import shutil
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

    def test_snapshot_restores_in_isolated_directory(self):
        with tempfile.TemporaryDirectory() as td:
            prior_dir, prior_db = server.DATA_DIR, server.DATABASE
            try:
                initial = Path(td) / "source"
                initial.mkdir()
                server.DATA_DIR = initial
                server.DATABASE = initial / "monitor.sqlite3"
                server.initialize()
                with server.db() as con:
                    con.execute("""INSERT INTO monitors
                        (name,kind,target,interval_seconds,timeout_seconds,created_at)
                        VALUES('Restore check','push','',60,8,?)""", (server.utcnow(),))
                    con.execute("""INSERT INTO maintenance
                        (title,description,starts_at,ends_at,created_at,public)
                        VALUES('Private window','Private details',
                               '2099-01-01T00:00:00+00:00','2099-01-01T01:00:00+00:00',?,0)""",
                                (server.utcnow(),))
                snapshot = Path(td) / "snapshot.sqlite3"
                backup.create_backup(snapshot)
                isolated = Path(td) / "isolated-restore"
                isolated.mkdir(mode=0o700)
                restored_file = isolated / "monitor.sqlite3"
                shutil.copyfile(snapshot, restored_file)
                os.chmod(restored_file, 0o600)
                server.DATA_DIR = isolated
                server.DATABASE = restored_file
                server.initialize()
                self.assertEqual(server.monitor_list()[0]["name"], "Restore check")
                with server.db() as con:
                    row = con.execute("SELECT title,public FROM maintenance").fetchone()
                    self.assertEqual((row["title"], row["public"]), ("Private window", 0))
                    self.assertEqual(con.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            finally:
                server.DATA_DIR, server.DATABASE = prior_dir, prior_db

    def test_backup_does_not_follow_existing_destination_symlink(self):
        with tempfile.TemporaryDirectory() as td:
            prior_dir, prior_db = server.DATA_DIR, server.DATABASE
            try:
                server.DATA_DIR = Path(td) / "data"
                server.DATABASE = server.DATA_DIR / "monitor.sqlite3"
                server.initialize()
                sensitive = Path(td) / "untouched.txt"
                sensitive.write_text("preserve this text")
                destination = Path(td) / "snapshot.sqlite3"
                destination.symlink_to(sensitive)
                with self.assertRaises(FileExistsError):
                    backup.create_backup(destination)
                self.assertEqual(sensitive.read_text(), "preserve this text")
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
