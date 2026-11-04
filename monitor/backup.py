"""Consistent, atomic SQLite backups for GoreeCloud Monitor.

Use only for an operator-controlled destination on local protected storage.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import os
from pathlib import Path
import sqlite3
import tempfile

from . import server


def create_backup(destination: Path) -> str:
    """Create a non-overwriting SQLite snapshot; return its SHA-256 hex digest."""
    source_path = server.DATABASE
    destination = destination.expanduser().absolute()
    if not source_path.is_file():
        raise FileNotFoundError("Monitor database does not exist")
    if not destination.parent.is_dir():
        raise FileNotFoundError("Backup destination directory does not exist")
    if destination.exists() or destination.is_symlink():
        raise FileExistsError("Backup destination already exists")

    fd, temporary = tempfile.mkstemp(prefix=".gc-monitor-backup-",
                                    suffix=".sqlite3", dir=destination.parent)
    try:
        os.fchmod(fd, 0o600)
        os.close(fd)
        fd = -1
        with closing(sqlite3.connect(source_path.as_uri() + "?mode=ro", uri=True,
                                     timeout=30)) as src:
            with closing(sqlite3.connect(temporary, timeout=30)) as dst:
                src.backup(dst)
                result = dst.execute("PRAGMA integrity_check").fetchone()[0]
                if result != "ok":
                    raise RuntimeError("Backup failed SQLite integrity check")
                dst.commit()
        # Same-directory hard-link creates the final destination atomically
        # without overwriting even if it appears after the initial check.
        os.link(temporary, destination)
    finally:
        if fd != -1:
            os.close(fd)
        Path(temporary).unlink(missing_ok=True)

    digest = hashlib.sha256()
    with destination.open("rb") as snapshot:
        for block in iter(lambda: snapshot.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a private, consistent Monitor SQLite backup")
    parser.add_argument("destination", type=Path, help="new .sqlite3 backup path (must not exist)")
    args = parser.parse_args()
    digest = create_backup(args.destination)
    print("Backup created:", args.destination)
    print("SHA-256:", digest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
