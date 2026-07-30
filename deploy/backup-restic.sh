#!/usr/bin/env bash
set -euo pipefail

# Encrypted off-server backups for Open Velojol.
#
# Expected production env file:
#   /opt/open-velojol/shared/backup.env
#
# The script creates a consistent SQLite copy with sqlite3 .backup, then sends
# that copy plus uploads to a restic repository such as Cloudflare R2.

APP_ROOT="${APP_ROOT:-/opt/open-velojol}"
ENV_FILE="${BACKUP_ENV_FILE:-$APP_ROOT/shared/backup.env}"

if [ -f "$ENV_FILE" ]; then
    set -a
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +a
fi

DB_PATH="${DB_PATH:-$APP_ROOT/current/instance/velojol.db}"
UPLOADS_DIR="${UPLOADS_DIR:-$APP_ROOT/current/app/static/uploads}"
LOCAL_BACKUP_DIR="${LOCAL_BACKUP_DIR:-$APP_ROOT/backups/restic-staging}"
RESTIC_TAG="${RESTIC_TAG:-open-velojol}"
BACKUP_KEEP_DAILY="${BACKUP_KEEP_DAILY:-14}"
BACKUP_KEEP_WEEKLY="${BACKUP_KEEP_WEEKLY:-8}"
BACKUP_KEEP_MONTHLY="${BACKUP_KEEP_MONTHLY:-12}"
BACKUP_INCLUDE_ENV="${BACKUP_INCLUDE_ENV:-false}"
HEALTHCHECK_URL="${HEALTHCHECK_URL:-}"

log() {
    echo "[backup-restic] $*"
}

ping_healthcheck() {
    local suffix="${1:-}"
    if [ -n "$HEALTHCHECK_URL" ] && command -v curl >/dev/null 2>&1; then
        curl -fsS -m 10 --retry 3 "$HEALTHCHECK_URL$suffix" >/dev/null || true
    fi
}

fail() {
    local exit_code=$?
    log "ERROR: backup failed with exit code $exit_code"
    ping_healthcheck "/fail"
    exit "$exit_code"
}

trap fail ERR

require_command() {
    if ! command -v "$1" >/dev/null 2>&1; then
        log "ERROR: required command is not installed: $1" >&2
        exit 1
    fi
}

require_command sqlite3
require_command restic

if [ -z "${RESTIC_REPOSITORY:-}" ]; then
    log "ERROR: RESTIC_REPOSITORY is not configured. Create $ENV_FILE from deploy/backup.env.example." >&2
    exit 1
fi

if [ -z "${RESTIC_PASSWORD:-}" ] && [ -z "${RESTIC_PASSWORD_FILE:-}" ]; then
    log "ERROR: RESTIC_PASSWORD or RESTIC_PASSWORD_FILE is required." >&2
    exit 1
fi

if [ ! -f "$DB_PATH" ]; then
    log "ERROR: SQLite database not found: $DB_PATH" >&2
    exit 1
fi

if [ ! -d "$UPLOADS_DIR" ]; then
    log "WARN: uploads directory not found, creating empty directory: $UPLOADS_DIR"
    mkdir -p "$UPLOADS_DIR"
fi

umask 077
mkdir -p "$LOCAL_BACKUP_DIR"
TEMP_DIR="$(mktemp -d "$LOCAL_BACKUP_DIR/open-velojol.XXXXXXXXXX")"

cleanup() {
    rm -rf "$TEMP_DIR"
}
trap cleanup EXIT
trap fail ERR

ping_healthcheck "/start"

TIMESTAMP="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
DB_COPY="$TEMP_DIR/velojol.db"
MANIFEST="$TEMP_DIR/manifest.txt"

log "Creating consistent SQLite backup from $DB_PATH"
sqlite3 "$DB_PATH" ".backup '$DB_COPY'"

cat > "$MANIFEST" <<EOF
app=open-velojol
created_at_utc=$TIMESTAMP
db_path=$DB_PATH
uploads_dir=$UPLOADS_DIR
host=$(hostname)
EOF

BACKUP_PATHS=("velojol.db" "manifest.txt" "$UPLOADS_DIR")

if [ "$BACKUP_INCLUDE_ENV" = "true" ]; then
    SHARED_ENV="$APP_ROOT/shared/.env"
    if [ -f "$SHARED_ENV" ]; then
        BACKUP_PATHS+=("$SHARED_ENV")
    else
        log "WARN: BACKUP_INCLUDE_ENV=true, but env file not found: $SHARED_ENV"
    fi
fi

log "Checking restic repository"
if ! restic snapshots >/dev/null 2>&1; then
    log "Repository is not initialized yet; running restic init"
    restic init
fi

log "Uploading encrypted backup to restic repository"
cd "$TEMP_DIR"
restic backup \
    --tag "$RESTIC_TAG" \
    --tag "sqlite" \
    --tag "uploads" \
    "${BACKUP_PATHS[@]}"

log "Applying retention policy: daily=$BACKUP_KEEP_DAILY weekly=$BACKUP_KEEP_WEEKLY monthly=$BACKUP_KEEP_MONTHLY"
restic forget \
    --tag "$RESTIC_TAG" \
    --keep-daily "$BACKUP_KEEP_DAILY" \
    --keep-weekly "$BACKUP_KEEP_WEEKLY" \
    --keep-monthly "$BACKUP_KEEP_MONTHLY" \
    --prune

log "Latest restic snapshots"
restic snapshots --tag "$RESTIC_TAG" --compact

ping_healthcheck
log "Backup completed successfully"
