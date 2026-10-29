#!/usr/bin/env python3
"""Private, SQLite-aware Uptime Kuma backup; run in ephemeral Python container."""
import argparse
import datetime
import hashlib
import io
import json
import os
from pathlib import Path
import secrets
import shutil
import sqlite3
import sys
import tarfile
import tempfile

EXCLUDE = {"kuma.db", "kuma.db-wal", "kuma.db-shm", "kuma.db-journal"}
VERSION = "goreecloud-kuma-backup-v1"


def digest(path):
    h = hashlib.sha256()
    length = 0
    with path.open("rb") as stream:
        while chunk := stream.read(1048576):
            h.update(chunk)
            length += len(chunk)
    return {"sha256": h.hexdigest(), "bytes": length}


def snapshot(source, staging):
    if not (source / "kuma.db").is_file():
        raise ValueError("Missing Kuma SQLite database")
    staging.mkdir(mode=0o700)
    with sqlite3.connect((source / "kuma.db").as_uri() + "?mode=ro", uri=True) as db:
        with sqlite3.connect(staging / "kuma.db") as backup_db:
            db.backup(backup_db, pages=64, sleep=0.1)
    for item in sorted(source.rglob("*")):
        if item.is_symlink():
            raise ValueError("Refusing source symlink")
        relative = item.relative_to(source)
        if relative.as_posix() in EXCLUDE or item.is_dir():
            continue
        if not item.is_file():
            raise ValueError("Unsupported source entry")
        target = staging / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(item, target)
        target.chmod(0o600)
    return {p.relative_to(staging).as_posix(): digest(p)
            for p in sorted(staging.rglob("*")) if p.is_file()}


def verify(archive_path):
    if not archive_path.is_file() or archive_path.is_symlink():
        raise ValueError("Backup archive missing")
    with tempfile.TemporaryDirectory(prefix="kuma-recovery-") as temp:
        root = Path(temp)
        actual = {}
        manifest = None
        with tarfile.open(archive_path, "r:gz") as archive:
            for item in archive:
                parts = Path(item.name).parts
                if not item.isfile() or item.issym() or item.islnk() or any(p in (".", "..") for p in parts) or item.name.startswith("/"):
                    raise ValueError("Unsafe archive entry")
                stream = archive.extractfile(item)
                if item.name == "manifest.json":
                    if manifest is not None or item.size > 5_000_000:
                        raise ValueError("Invalid manifest")
                    manifest = json.load(stream)
                    continue
                if not item.name.startswith("data/") or len(parts) < 2:
                    raise ValueError("Unexpected archive path")
                name = item.name[5:]
                if name in actual:
                    raise ValueError("Duplicate entry")
                output = root / name
                output.parent.mkdir(parents=True, exist_ok=True)
                h = hashlib.sha256()
                size = 0
                with output.open("wb") as dest:
                    while chunk := stream.read(1048576):
                        h.update(chunk)
                        size += len(chunk)
                        dest.write(chunk)
                actual[name] = {"sha256": h.hexdigest(), "bytes": size}
        if not isinstance(manifest, dict) or manifest.get("version") != VERSION or manifest.get("files") != actual or "kuma.db" not in actual:
            raise ValueError("Backup hash mismatch")
        with sqlite3.connect((root / "kuma.db").as_uri() + "?mode=ro", uri=True) as db:
            if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("Restored database integrity check failed")
        print("RESTORE_VERIFIED", len(actual), "files")


def backup(source, output_dir):
    if not source.is_dir() or source.is_symlink():
        raise ValueError("Source directory missing")
    if not output_dir.is_dir() or output_dir.is_symlink() or output_dir.stat().st_mode & 0o077:
        raise PermissionError("Backup directory must exist with mode 0700")
    filename = datetime.datetime.now(datetime.timezone.utc).strftime("kuma-%Y%m%dT%H%M%SZ-") + secrets.token_hex(4) + ".tar.gz"
    path = output_dir / filename
    with tempfile.TemporaryDirectory(prefix="kuma-snapshot-") as temp:
        stage = Path(temp) / "data"
        files = snapshot(source, stage)
        body = json.dumps({"version": VERSION, "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "files": files}, sort_keys=True).encode()
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, "wb") as destination:
                with tarfile.open(fileobj=destination, mode="w:gz") as archive:
                    info = tarfile.TarInfo("manifest.json")
                    info.size, info.mode = len(body), 0o600
                    archive.addfile(info, io.BytesIO(body))
                    for name in files:
                        archive.add(stage / name, arcname="data/" + name, recursive=False)
        except Exception:
            path.unlink(missing_ok=True)
            raise
    verify(path)
    print("BACKUP_OK", filename)


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="action", required=True)
    b = sub.add_parser("backup")
    b.add_argument("--source", type=Path, default=Path("/source"))
    b.add_argument("--destination", type=Path, default=Path("/backups"))
    v = sub.add_parser("verify")
    v.add_argument("archive", type=Path)
    a = p.parse_args()
    if a.action == "backup":
        backup(a.source, a.destination)
    else:
        verify(a.archive)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("Backup operation failed:", type(error).__name__, file=sys.stderr)
        sys.exit(1)
