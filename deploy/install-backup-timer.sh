#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "[install] Installing backup script"
cp "$SCRIPT_DIR/velojol-backup.sh" /usr/local/bin/velojol-backup.sh
chmod +x /usr/local/bin/velojol-backup.sh

echo "[install] Installing systemd unit files"
cp "$SCRIPT_DIR/velojol-backup.service" /etc/systemd/system/velojol-backup.service
cp "$SCRIPT_DIR/velojol-backup.timer" /etc/systemd/system/velojol-backup.timer

echo "[install] Reloading systemd"
systemctl daemon-reload

echo "[install] Enabling daily backup timer"
systemctl enable --now velojol-backup.timer

echo "[install] Running test backup"
systemctl start velojol-backup.service

echo "[install] Timer status"
systemctl status velojol-backup.timer --no-pager -l

echo "[install] Backup directory contents"
ls -lah /opt/open-velojol/backups
