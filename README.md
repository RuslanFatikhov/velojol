# Velojol

## Backup Timer

Daily SQLite backup files live in:

- `/opt/open-velojol/backups`

Install the backup timer on the server:

```bash
cd /opt/open-velojol/current
bash deploy/install-backup-timer.sh
```

Check the timer and run a manual backup:

```bash
systemctl list-timers | grep velojol
systemctl status velojol-backup.timer --no-pager -l
systemctl start velojol-backup.service
ls -lah /opt/open-velojol/backups
```

## Safe Deploy

Use `rsync` only against `/opt/open-velojol/current/`.

Never overwrite:

- `/opt/open-velojol/current/instance/`
- `/opt/open-velojol/backups/`

Safe deploy command:

```bash
rsync -avz \
  --exclude '.git' \
  --exclude '.DS_Store' \
  --exclude '__pycache__' \
  --exclude '.venv' \
  --exclude 'open-velojol-env/' \
  --exclude 'venv' \
  --exclude 'instance/' \
  --exclude 'backups/' \
  --exclude '*.db' \
  --exclude '*.sqlite' \
  --exclude '*.sqlite3' \
  ./ root@31.130.152.60:/opt/open-velojol/current/
```

## Backup Restore

```bash
systemctl stop velojol-gunicorn.service

cp /opt/open-velojol/current/instance/velojol.db \
  /opt/open-velojol/current/instance/velojol.db.before-restore.$(date +"%Y-%m-%d_%H-%M-%S")

cp /opt/open-velojol/backups/velojol.db.YYYY-MM-DD_HH-MM-SS.backup \
  /opt/open-velojol/current/instance/velojol.db

systemctl start velojol-gunicorn.service
```

## Server Runtime Repair

If the server lost `/opt/open-velojol/current`, has a broken virtualenv, or accidentally received a macOS `.venv`, run:

```bash
cd /opt/open-velojol
bash deploy/repair-server-runtime.sh
```

More detail: [deploy/README.md](deploy/README.md)
