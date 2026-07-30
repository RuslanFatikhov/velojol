#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ROOT="${APP_ROOT:-/opt/open-velojol}"
SHARED_DIR="$APP_ROOT/shared"
ENV_FILE="$SHARED_DIR/backup.env"
RUN_NOW=false

for arg in "$@"; do
    case "$arg" in
        --run-now)
            RUN_NOW=true
            ;;
        -h|--help)
            echo "Usage: $0 [--run-now]"
            echo
            echo "Installs the Open Velojol restic backup timer."
            echo "Create $ENV_FILE from deploy/backup.env.example before running --run-now."
            exit 0
            ;;
        *)
            echo "[install] ERROR: unknown argument: $arg" >&2
            exit 1
            ;;
    esac
done

if [ "$(id -u)" -ne 0 ]; then
    echo "[install] ERROR: run this script as root" >&2
    exit 1
fi

echo "[install] Installing restic backup script"
cp "$SCRIPT_DIR/backup-restic.sh" /usr/local/bin/velojol-backup-restic.sh
chmod 700 /usr/local/bin/velojol-backup-restic.sh

echo "[install] Installing systemd unit files"
cp "$SCRIPT_DIR/systemd/velojol-backup.service" /etc/systemd/system/velojol-backup.service
cp "$SCRIPT_DIR/systemd/velojol-backup.timer" /etc/systemd/system/velojol-backup.timer

mkdir -p "$SHARED_DIR"
if [ ! -f "$ENV_FILE" ]; then
    echo "[install] Creating backup env template: $ENV_FILE"
    cp "$SCRIPT_DIR/backup.env.example" "$ENV_FILE"
    chmod 600 "$ENV_FILE"
    echo "[install] IMPORTANT: edit $ENV_FILE and fill RESTIC_REPOSITORY, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, RESTIC_PASSWORD"
else
    echo "[install] Existing backup env kept: $ENV_FILE"
    chmod 600 "$ENV_FILE"
fi

echo "[install] Reloading systemd"
systemctl daemon-reload

echo "[install] Enabling daily backup timer"
systemctl enable --now velojol-backup.timer

if [ "$RUN_NOW" = "true" ]; then
    echo "[install] Running test backup"
    systemctl start velojol-backup.service
else
    echo "[install] Skipping test backup. Run after filling $ENV_FILE:"
    echo "          systemctl start velojol-backup.service"
fi

echo "[install] Timer status"
systemctl status velojol-backup.timer --no-pager -l
