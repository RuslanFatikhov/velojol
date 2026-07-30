#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_ENV_FILE="$SCRIPT_DIR/.deploy.env"

if [[ -f "$DEPLOY_ENV_FILE" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$DEPLOY_ENV_FILE"
    set +a
fi

REMOTE_APP_ROOT="${REMOTE_APP_ROOT:-/opt/open-velojol}"
REMOTE_CURRENT="${REMOTE_CURRENT:-/opt/open-velojol/current}"
SERVICE_NAME="${SERVICE_NAME:-velojol-gunicorn.service}"
HEALTHCHECK_URL="${HEALTHCHECK_URL:-http://127.0.0.1:8020}"
DEPLOY_TARGET="${DEPLOY_TARGET:-}"
DEPLOY_MODE="${1:-}"
FAILED_STAGE="initialization"
REMOTE_CODE_BACKUP="not created"
REMOTE_DB_BACKUP="not created"

report_failure() {
    local exit_code=$?
    if [[ "$exit_code" -eq 0 ]]; then
        return
    fi
    printf 'DEPLOY FAILED during: %s\n' "$FAILED_STAGE" >&2
    printf 'Code backup: %s\n' "$REMOTE_CODE_BACKUP" >&2
    printf 'Database backup: %s\n' "$REMOTE_DB_BACKUP" >&2
}
trap report_failure EXIT

usage() {
    printf 'Usage: %s --dry-run | --apply\n' "${0##*/}"
}

if [[ "$DEPLOY_MODE" != "--dry-run" && "$DEPLOY_MODE" != "--apply" ]]; then
    usage >&2
    exit 2
fi

if [[ -z "$DEPLOY_TARGET" ]]; then
    printf 'DEPLOY_TARGET is required. Copy .deploy.env.example to .deploy.env.\n' >&2
    exit 2
fi

if [[ "$DEPLOY_TARGET" =~ [[:space:]] ]]; then
    printf 'DEPLOY_TARGET must not contain whitespace.\n' >&2
    exit 2
fi

if [[ "$REMOTE_APP_ROOT" != /* || "$REMOTE_CURRENT" != "$REMOTE_APP_ROOT"/* ]]; then
    printf 'REMOTE_CURRENT must be an absolute child of REMOTE_APP_ROOT.\n' >&2
    exit 2
fi

run_remote_read_checks() {
    ssh "$DEPLOY_TARGET" bash -s -- "$REMOTE_APP_ROOT" "$REMOTE_CURRENT" <<'REMOTE'
set -Eeuo pipefail
remote_root=$1
remote_current=$2

[[ "$remote_root" == /opt/open-velojol || "$remote_root" == /* ]]
[[ "$remote_current" == "$remote_root"/* ]]
test -d "$remote_root"
test -d "$remote_current"
test -f "$remote_current/run.py"
test -f "$remote_current/requirements.txt"
command -v rsync >/dev/null
command -v sqlite3 >/dev/null

db_link="$remote_current/instance/velojol.db"
db_path=$(readlink -f "$db_link")
test -n "$db_path"
test -f "$db_path"
case "$db_path" in
    "$remote_root"/*) ;;
    *) printf 'Database resolves outside REMOTE_APP_ROOT: %s\n' "$db_path" >&2; exit 1 ;;
esac
printf 'Remote paths verified. Database: %s\n' "$db_path"
REMOTE
}

create_remote_backups() {
    local timestamp=$1
    local backup_dir="$REMOTE_APP_ROOT/backups/deploy-$timestamp"
    REMOTE_CODE_BACKUP="$backup_dir/open-velojol-code-$timestamp.tar.gz"
    REMOTE_DB_BACKUP="$backup_dir/velojol-$timestamp.sqlite3"

    ssh "$DEPLOY_TARGET" bash -s -- \
        "$REMOTE_APP_ROOT" \
        "$REMOTE_CURRENT" \
        "$backup_dir" \
        "$REMOTE_CODE_BACKUP" \
        "$REMOTE_DB_BACKUP" <<'REMOTE'
set -Eeuo pipefail
remote_root=$1
remote_current=$2
backup_dir=$3
code_backup=$4
db_backup=$5

db_path=$(readlink -f "$remote_current/instance/velojol.db")
test -n "$db_path"
test -f "$db_path"
case "$db_path" in
    "$remote_root"/*) ;;
    *) printf 'Refusing to back up unexpected database path: %s\n' "$db_path" >&2; exit 1 ;;
esac

mkdir -p "$backup_dir"
tar \
    --exclude='./instance' \
    --exclude='./app/static/uploads' \
    --exclude='./backups' \
    --exclude='./server-backups' \
    --exclude='*.db' \
    --exclude='*.sqlite' \
    --exclude='*.sqlite3' \
    -C "$remote_current" \
    -czf "$code_backup" \
    .
sqlite3 "$db_path" ".backup '$db_backup'"
test -s "$code_backup"
test -s "$db_backup"
printf 'Code backup: %s\nDatabase backup: %s\n' "$code_backup" "$db_backup"
REMOTE
}

rsync_release() {
    local rsync_args=(
        -az
        --chmod=Dugo+rx,Fu+rw,Fgo+r
        --exclude='.git/'
        --exclude='.env'
        --exclude='.env.*'
        --exclude='.deploy.env'
        --exclude='.DS_Store'
        --exclude='._*'
        --exclude='__pycache__/'
        --exclude='*.pyc'
        --exclude='*.pyo'
        --exclude='.pytest_cache/'
        --exclude='.venv/'
        --exclude='venv/'
        --exclude='open-velojol-env/'
        --exclude='instance/'
        --exclude='*.db'
        --exclude='*.sqlite'
        --exclude='*.sqlite3'
        --exclude='backups/'
        --exclude='server-backups/'
        --exclude='app/static/uploads/'
    )
    if [[ "$DEPLOY_MODE" == "--dry-run" ]]; then
        rsync_args+=(--dry-run --itemize-changes)
    fi

    rsync "${rsync_args[@]}" \
        "$SCRIPT_DIR/" "$DEPLOY_TARGET:$REMOTE_CURRENT/"
}

run_remote_release_steps() {
    ssh "$DEPLOY_TARGET" bash -s -- \
        "$REMOTE_APP_ROOT" \
        "$REMOTE_CURRENT" \
        "$SERVICE_NAME" \
        "$HEALTHCHECK_URL" <<'REMOTE'
set -Eeuo pipefail
remote_root=$1
remote_current=$2
service_name=$3
healthcheck_url=$4
venv="$remote_root/open-velojol-env"

test -x "$venv/bin/python"
test -x "$venv/bin/pip"
cd "$remote_current"
"$venv/bin/pip" install -r requirements.txt
FLASK_APP=run.py "$venv/bin/flask" db upgrade
systemctl restart "$service_name"

for attempt in $(seq 1 15); do
    if ! systemctl is-active --quiet "$service_name"; then
        systemctl status "$service_name" --no-pager -l >&2 || true
        journalctl -u "$service_name" -n 80 --no-pager >&2 || true
        exit 1
    fi

    if "$venv/bin/python" scripts/healthcheck.py --base-url "$healthcheck_url"; then
        exit 0
    fi

    if [[ "$attempt" -lt 15 ]]; then
        printf 'Health check is not ready yet (%s/15); retrying in 2 seconds...\n' "$attempt"
        sleep 2
    fi
done

systemctl status "$service_name" --no-pager -l >&2 || true
journalctl -u "$service_name" -n 80 --no-pager >&2 || true
exit 1
REMOTE
}

printf 'Mode: %s\nTarget: %s\nRemote current: %s\n' "$DEPLOY_MODE" "$DEPLOY_TARGET" "$REMOTE_CURRENT"

FAILED_STAGE="local preflight"
if [[ -x "$SCRIPT_DIR/.venv/bin/python" ]]; then
    PYTHONPYCACHEPREFIX=/private/tmp/velojol-preflight-pycache \
        "$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/scripts/preflight_check.py" "$SCRIPT_DIR"
else
    PYTHONPYCACHEPREFIX=/private/tmp/velojol-preflight-pycache \
        python3 "$SCRIPT_DIR/scripts/preflight_check.py" "$SCRIPT_DIR"
fi

FAILED_STAGE="SSH connectivity and remote path verification"
run_remote_read_checks

if [[ "$DEPLOY_MODE" == "--apply" ]]; then
    FAILED_STAGE="remote code and SQLite backups"
    create_remote_backups "$(date -u +'%Y%m%dT%H%M%SZ')"
else
    printf 'Dry-run: no remote backups created and no server state changed.\n'
fi

FAILED_STAGE="rsync upload"
rsync_release

if [[ "$DEPLOY_MODE" == "--dry-run" ]]; then
    trap - EXIT
    printf 'DRY-RUN OK: no production changes were applied.\n'
    exit 0
fi

FAILED_STAGE="remote dependencies, migration, restart, and health check"
run_remote_release_steps

trap - EXIT
printf 'DEPLOY OK\nCode backup: %s\nDatabase backup: %s\n' \
    "$REMOTE_CODE_BACKUP" "$REMOTE_DB_BACKUP"
