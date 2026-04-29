#!/usr/bin/env python3
import argparse
import json
import os
import shutil
import sqlite3
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Create a backup of the Velojol SQLite database and user uploads."
    )
    parser.add_argument(
        "--app-root",
        default=os.environ.get("APP_ROOT", "."),
        help="Application root used to resolve default paths.",
    )
    parser.add_argument(
        "--db-path",
        help="Path to SQLite database. Defaults to shared/instance/velojol.db for deploys or instance/velojol.db locally.",
    )
    parser.add_argument(
        "--uploads-dir",
        help="Path to user uploads directory. Defaults to shared/uploads for deploys or app/static/uploads locally.",
    )
    parser.add_argument(
        "--backup-dir",
        help="Directory where backup archives will be stored. Defaults to shared/backups or backups locally.",
    )
    parser.add_argument(
        "--keep-count",
        type=int,
        default=int(os.environ.get("BACKUP_KEEP_COUNT", "14")),
        help="Number of most recent backup archives to keep.",
    )
    return parser.parse_args()


def resolve_default_paths(app_root: Path):
    shared_root = app_root / "shared"
    if shared_root.exists():
        return (
            shared_root / "instance" / "velojol.db",
            shared_root / "uploads",
            shared_root / "backups",
        )

    return (
        app_root / "instance" / "velojol.db",
        app_root / "app" / "static" / "uploads",
        app_root / "backups",
    )


def ensure_exists(path: Path, label: str):
    if not path.exists():
        raise FileNotFoundError(f"{label} not found: {path}")


def backup_sqlite(source_path: Path, target_path: Path):
    source = sqlite3.connect(f"file:{source_path}?mode=ro", uri=True)
    try:
        target = sqlite3.connect(target_path)
        try:
            source.backup(target)
        finally:
            target.close()
    finally:
        source.close()


def write_manifest(manifest_path: Path, db_path: Path, uploads_dir: Path, archive_name: str):
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "archive_name": archive_name,
        "database_path": str(db_path),
        "uploads_dir": str(uploads_dir),
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_archive(archive_path: Path, db_copy_path: Path, uploads_dir: Path, manifest_path: Path):
    with tarfile.open(archive_path, "w:gz") as archive:
        archive.add(db_copy_path, arcname="instance/velojol.db")
        archive.add(uploads_dir, arcname="uploads")
        archive.add(manifest_path, arcname="manifest.json")


def rotate_backups(backup_dir: Path, keep_count: int):
    archives = sorted(backup_dir.glob("velojol-backup-*.tar.gz"), reverse=True)
    for archive in archives[keep_count:]:
        archive.unlink()


def main():
    args = parse_args()
    app_root = Path(args.app_root).resolve()
    default_db_path, default_uploads_dir, default_backup_dir = resolve_default_paths(app_root)

    db_path = Path(args.db_path).resolve() if args.db_path else default_db_path
    uploads_dir = Path(args.uploads_dir).resolve() if args.uploads_dir else default_uploads_dir
    backup_dir = Path(args.backup_dir).resolve() if args.backup_dir else default_backup_dir

    ensure_exists(db_path, "Database")
    ensure_exists(uploads_dir, "Uploads directory")
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    archive_name = f"velojol-backup-{timestamp}.tar.gz"
    archive_path = backup_dir / archive_name

    with tempfile.TemporaryDirectory(prefix="velojol-backup-", dir=str(backup_dir)) as temp_dir:
        temp_root = Path(temp_dir)
        db_copy_path = temp_root / "velojol.db"
        manifest_path = temp_root / "manifest.json"

        backup_sqlite(db_path, db_copy_path)
        write_manifest(manifest_path, db_path, uploads_dir, archive_name)
        build_archive(archive_path, db_copy_path, uploads_dir, manifest_path)

    rotate_backups(backup_dir, args.keep_count)
    print(json.dumps({"status": "ok", "archive": str(archive_path), "kept": args.keep_count}))


if __name__ == "__main__":
    main()
