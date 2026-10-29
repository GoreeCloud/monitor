import pathlib
import sqlite3
import tempfile
import unittest
from kuma_backup import backup, verify


class BackupTest(unittest.TestCase):
    def test_offline_fixture_and_recovery(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            source = root / "source"
            destination = root / "backup"
            source.mkdir()
            destination.mkdir(mode=0o700)
            with sqlite3.connect(source / "kuma.db") as db:
                db.execute("CREATE TABLE synthetic(id INTEGER, state TEXT)")
                db.execute("INSERT INTO synthetic VALUES (1, 'UP')")
            (source / "db-config.json").write_text('{"type":"sqlite"}')
            (source / "upload").mkdir()
            (source / "upload" / "example").write_text("test")
            backup(source, destination)
            snapshots = list(destination.glob("kuma-*.tar.gz"))
            self.assertEqual(len(snapshots), 1)
            self.assertEqual(snapshots[0].stat().st_mode & 0o777, 0o600)
            verify(snapshots[0])

    def test_private_permissions_required(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            src, dst = root / "source", root / "backup"
            src.mkdir()
            dst.mkdir(mode=0o755)
            with self.assertRaises(PermissionError):
                backup(src, dst)


if __name__ == "__main__":
    unittest.main()
