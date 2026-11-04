"""WAL-consistency and failure-cleanup acceptance for offline backup recovery.

All databases, WAL files, snapshots and restore directories are ephemeral.
This does not inspect or alter any live GoreeCloud backup.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import sqlite3
import stat
import tempfile
import unittest

from monitor import backup, server


class WALBackupAcceptance(unittest.TestCase):
    def test_snapshot_keeps_committed_wal_and_excludes_uncommitted_transaction(self):
        with tempfile.TemporaryDirectory(prefix="gc-monitor-wal-") as work:
            original = (server.DATA_DIR, server.DATABASE)
            writer = None
            try:
                root = Path(work)
                server.DATA_DIR = root / "source"
                server.DATABASE = server.DATA_DIR / "monitor.sqlite3"
                server.initialize()
                writer = sqlite3.connect(server.DATABASE, timeout=5)
                writer.execute("PRAGMA wal_autocheckpoint=0")
                self.assertEqual(
                    writer.execute("PRAGMA journal_mode").fetchone()[0], "wal")
                writer.execute(
                    """INSERT INTO monitors
                    (name,kind,target,interval_seconds,timeout_seconds,created_at)
                    VALUES('WAL committed','push','',60,8,?)""",
                    (server.utcnow(),),
                )
                writer.execute(
                    """INSERT INTO maintenance
                    (title,description,starts_at,ends_at,created_at,public)
                    VALUES('Private snapshot','fixture details',
                    '2099-01-01T00:00:00+00:00','2099-01-01T01:00:00+00:00',?,0)""",
                    (server.utcnow(),),
                )
                writer.commit()
                wal = Path(str(server.DATABASE) + "-wal")
                self.assertTrue(wal.is_file() and wal.stat().st_size > 0,
                                "committed state must still be in a WAL file")
                writer.execute("BEGIN IMMEDIATE")
                writer.execute(
                    """INSERT INTO monitors
                    (name,kind,target,interval_seconds,timeout_seconds,created_at)
                    VALUES('WAL uncommitted','push','',60,8,?)""",
                    (server.utcnow(),),
                )
                destination = root / "consistent-snapshot.sqlite3"
                digest = backup.create_backup(destination)
                self.assertEqual(
                    digest, hashlib.sha256(destination.read_bytes()).hexdigest())
                self.assertEqual(stat.S_IMODE(destination.stat().st_mode), 0o600)
                with sqlite3.connect(destination) as snap:
                    self.assertEqual(snap.execute(
                        "PRAGMA integrity_check").fetchone()[0], "ok")
                    rows = [r[0] for r in snap.execute(
                        "SELECT name FROM monitors ORDER BY id")]
                    self.assertEqual(rows, ["WAL committed"])
                    maintenance = snap.execute(
                        "SELECT title,public FROM maintenance").fetchone()
                    self.assertEqual(maintenance, ("Private snapshot", 0))

                # Restore from the single-file snapshot, not from live WAL/SHM.
                restored_dir = root / "isolated-restore"
                restored_dir.mkdir(mode=0o700)
                restored_path = restored_dir / "monitor.sqlite3"
                shutil.copyfile(destination, restored_path)
                os.chmod(restored_path, 0o600)
                writer.rollback()
                writer.close()
                writer = None
                server.DATA_DIR = restored_dir
                server.DATABASE = restored_path
                server.initialize()
                self.assertEqual(
                    [r["name"] for r in server.monitor_list()],
                    ["WAL committed"])
                with server.db() as con:
                    self.assertEqual(
                        con.execute("SELECT COUNT(*) FROM maintenance "
                                    "WHERE public=0").fetchone()[0], 1)
                    self.assertEqual(
                        con.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            finally:
                if writer is not None:
                    writer.rollback()
                    writer.close()
                server.DATA_DIR, server.DATABASE = original

    def test_corrupt_source_leaves_no_published_or_temporary_snapshot(self):
        with tempfile.TemporaryDirectory(prefix="gc-monitor-wal-failure-") as work:
            original = server.DATABASE
            try:
                root = Path(work)
                corrupt = root / "corrupt.sqlite3"
                corrupt.write_bytes(b"intentionally invalid sqlite fixture")
                server.DATABASE = corrupt
                target = root / "should-not-exist.sqlite3"
                with self.assertRaises(sqlite3.DatabaseError):
                    backup.create_backup(target)
                self.assertFalse(target.exists())
                self.assertEqual(
                    list(root.glob(".gc-monitor-backup-*.sqlite3")), [])
                self.assertEqual(
                    corrupt.read_bytes(), b"intentionally invalid sqlite fixture")
            finally:
                server.DATABASE = original


if __name__ == "__main__":
    unittest.main()
