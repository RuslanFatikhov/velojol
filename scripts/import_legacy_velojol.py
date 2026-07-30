#!/usr/bin/env python3
"""Dry-run and apply the local velojol.kz legacy archive migration."""

import argparse
from datetime import datetime
import json
from pathlib import Path
import sqlite3
import sys


def parse_args():
    parser = argparse.ArgumentParser(
        description='Import cities, bikelanes and photos from the original velojol.kz archive.'
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--dry-run', action='store_true', help='Build a report without writes')
    mode.add_argument('--apply', action='store_true', help='Apply safe plan items')
    parser.add_argument('--source-root', required=True, help='Path to the legacy public_html')
    parser.add_argument(
        '--database',
        help='SQLite database path; defaults to instance/velojol.db',
    )
    parser.add_argument(
        '--static-root',
        help='Override destination static directory (useful for isolated testing)',
    )
    parser.add_argument('--report', help='Optional JSON report path')
    parser.add_argument(
        '--backup-dir',
        help='Backup directory for --apply; defaults beside the database',
    )
    parser.add_argument(
        '--spatial-tolerance',
        type=float,
        default=20,
        help='Spatial matching tolerance in meters (default: 20)',
    )
    parser.add_argument(
        '--no-merge-osm',
        action='store_true',
        help='Leave high-confidence OSM matches for manual review',
    )
    parser.add_argument(
        '--no-copy-photos',
        action='store_true',
        help='Do not copy legacy photos or city images during --apply',
    )
    return parser.parse_args()


def sqlite_uri(path):
    return f'sqlite:///{path}'


def backup_sqlite(database_path, backup_dir=None):
    database_path = Path(database_path).expanduser().resolve()
    if not database_path.is_file():
        raise RuntimeError(f'База данных не найдена: {database_path}')
    target_dir = (
        Path(backup_dir).expanduser().resolve()
        if backup_dir
        else database_path.parent / 'migration-backups'
    )
    target_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    destination = target_dir / f'{database_path.stem}.before-legacy-import.{timestamp}.db'
    with sqlite3.connect(database_path) as source:
        with sqlite3.connect(destination) as target:
            source.backup(target)
    return destination


def ensure_schema(db):
    from sqlalchemy import inspect

    columns = {column['name'] for column in inspect(db.engine).get_columns('bikelanes')}
    missing = {'external_id', 'source_metadata'} - columns
    if missing:
        names = ', '.join(sorted(missing))
        raise RuntimeError(
            f'В bikelanes отсутствуют поля {names}. Сначала выполните: flask db upgrade'
        )


def write_report(path, payload):
    if not path:
        return
    report_path = Path(path).expanduser().resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8',
    )


def print_summary(summary):
    print('LEGACY VELOJOL IMPORT PLAN')
    for key in (
        'cities',
        'records',
        'new',
        'merge_osm',
        'refresh_legacy',
        'review',
        'invalid',
        'photo_files',
        'archive_photo_files',
        'unassigned_photo_files',
        'archive_issues',
    ):
        print(f'{key}: {summary.get(key, 0)}')


def main():
    args = parse_args()
    project_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(project_root))

    database_path = Path(args.database or project_root / 'instance' / 'velojol.db').resolve()

    from config import Config

    class ImportConfig(Config):
        SQLALCHEMY_DATABASE_URI = sqlite_uri(database_path)
        SQLALCHEMY_TRACK_MODIFICATIONS = False

    from app import create_app, db
    from app.services.legacy_import import (
        apply_legacy_import_plan,
        build_legacy_import_plan,
    )

    app = create_app(ImportConfig)
    if args.static_root:
        app.static_folder = str(Path(args.static_root).expanduser().resolve())
    payload = {}
    with app.app_context():
        ensure_schema(db)
        plan = build_legacy_import_plan(
            args.source_root,
            spatial_tolerance_meters=args.spatial_tolerance,
        )
        payload = plan.to_dict()
        print_summary(payload['summary'])

        if args.apply:
            backup_path = backup_sqlite(database_path, args.backup_dir)
            print(f'backup: {backup_path}')
            application = apply_legacy_import_plan(
                plan,
                merge_osm=not args.no_merge_osm,
                copy_photos=not args.no_copy_photos,
            )
            payload['application'] = application
            payload['backup'] = str(backup_path)
            print('APPLY RESULT')
            for key, value in application.items():
                if key != 'failures':
                    print(f'{key}: {value}')
            if application['failures']:
                print(f"failures: {len(application['failures'])}")

    write_report(args.report, payload)
    if args.report:
        print(f'report: {Path(args.report).expanduser().resolve()}')
    if payload.get('application', {}).get('failures'):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
