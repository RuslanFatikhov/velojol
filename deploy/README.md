# Production Deployment

## Backups

Repository files:

- `deploy/velojol-backup.sh`
- `deploy/velojol-backup.service`
- `deploy/velojol-backup.timer`
- `deploy/install-backup-timer.sh`

Server paths:

- project root: `/opt/open-velojol`
- running app: `/opt/open-velojol/current`
- SQLite database: `/opt/open-velojol/current/instance/velojol.db`
- backup directory: `/opt/open-velojol/backups`
- Python env: `/opt/open-velojol/open-velojol-env`
- gunicorn service: `velojol-gunicorn.service`

Install daily backups on the server:

```bash
cd /opt/open-velojol/current
bash deploy/install-backup-timer.sh
```

Check that the timer works:

```bash
systemctl list-timers | grep velojol
systemctl status velojol-backup.timer --no-pager -l
systemctl start velojol-backup.service
ls -lah /opt/open-velojol/backups
```

Repair server runtime after the first deploy or after a broken virtualenv:

```bash
cd /opt/open-velojol
bash deploy/repair-server-runtime.sh
```

## Безопасное обновление сервера без потери базы данных

Deploy code only into `/opt/open-velojol/current/`.

Never touch these paths during deploy:

- `/opt/open-velojol/current/instance/`
- `/opt/open-velojol/backups/`

Rules:

- do not upload the project into `/opt/open-velojol/`
- upload only into `/opt/open-velojol/current/`
- database must live only on the server
- local SQLite database must never be copied to the server

Use this safe `rsync` command:

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

After upload, update dependencies and restart the service on the server:

```bash
ssh root@31.130.152.60
cd /opt/open-velojol
bash deploy/repair-server-runtime.sh
/opt/open-velojol/open-velojol-env/bin/pip install -r /opt/open-velojol/requirements.txt
cd /opt/open-velojol/current
/opt/open-velojol/open-velojol-env/bin/pip install -r requirements.txt
systemctl restart velojol-gunicorn.service
systemctl status velojol-gunicorn.service --no-pager -l
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
