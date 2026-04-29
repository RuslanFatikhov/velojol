#!/usr/bin/env bash
set -euo pipefail

DB_PATH="/opt/open-velojol/current/instance/velojol.db"
BACKUP_DIR="/opt/open-velojol/backups"
TIMESTAMP="$(date +"%Y-%m-%d_%H-%M-%S")"
BACKUP_FILE="$BACKUP_DIR/velojol.db.$TIMESTAMP.backup"

echo "[backup] Starting Open.Velojol SQLite backup"
echo "[backup] Database: $DB_PATH"
echo "[backup] Backup dir: $BACKUP_DIR"

mkdir -p "$BACKUP_DIR"

if ! command -v sqlite3 >/dev/null 2>&1; then
    echo "[backup] ERROR: sqlite3 is not installed" >&2
    exit 1
fi

if [ ! -f "$DB_PATH" ]; then
    echo "[backup] ERROR: database file not found: $DB_PATH" >&2
    exit 1
fi

echo "[backup] Creating backup: $BACKUP_FILE"
sqlite3 "$DB_PATH" ".backup '$BACKUP_FILE'"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "[backup] ERROR: backup file was not created: $BACKUP_FILE" >&2
    exit 1
fi

echo "[backup] Removing old backups, keeping only 5 latest files"
ls -1t "$BACKUP_DIR"/velojol.db.*.backup 2>/dev/null | tail -n +6 | xargs -r rm -f

echo "[backup] Backup created successfully: $BACKUP_FILE"
echo "[backup] Current backups:"
ls -lah "$BACKUP_DIR"
