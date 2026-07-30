# Open Velojol backups

This project uses `restic` for encrypted off-server backups. The recommended
target is Cloudflare R2, but any S3-compatible storage works.

## What is backed up

- A consistent SQLite copy created with `sqlite3 .backup`.
- User uploads from `app/static/uploads`.
- A small manifest with timestamp, hostname, and source paths.

The application `.env` is not included by default. To include it in encrypted
backups, set `BACKUP_INCLUDE_ENV=true` in `/opt/open-velojol/shared/backup.env`.

## Server setup

Install required packages:

```bash
apt update
apt install -y sqlite3 curl restic
```

Install the timer:

```bash
cd /opt/open-velojol/current
bash deploy/install-backup-timer.sh
```

Edit the generated env file:

```bash
nano /opt/open-velojol/shared/backup.env
chmod 600 /opt/open-velojol/shared/backup.env
```

Required values:

```bash
RESTIC_REPOSITORY=s3:https://<account-id>.r2.cloudflarestorage.com/<bucket-name>
AWS_ACCESS_KEY_ID=<r2-access-key-id>
AWS_SECRET_ACCESS_KEY=<r2-secret-access-key>
AWS_DEFAULT_REGION=auto
AWS_REGION=auto
RESTIC_PASSWORD=<long-random-restic-password>
```

Run the first backup:

```bash
systemctl start velojol-backup.service
journalctl -u velojol-backup.service -n 120 --no-pager
```

Check the timer:

```bash
systemctl list-timers | grep velojol
systemctl status velojol-backup.timer --no-pager -l
```

## Retention

Default retention:

- 14 daily backups
- 8 weekly backups
- 12 monthly backups

Configure this in `/opt/open-velojol/shared/backup.env`:

```bash
BACKUP_KEEP_DAILY=14
BACKUP_KEEP_WEEKLY=8
BACKUP_KEEP_MONTHLY=12
```

## Restore drill

List snapshots:

```bash
source /opt/open-velojol/shared/backup.env
restic snapshots --tag open-velojol
```

Restore the latest snapshot to a temporary directory:

```bash
mkdir -p /tmp/open-velojol-restore-test
restic restore latest --tag open-velojol --target /tmp/open-velojol-restore-test
find /tmp/open-velojol-restore-test -maxdepth 4 -type f | head
```

The restored SQLite copy will be named `velojol.db`.

Before replacing production data, stop the app and make a local safety copy:

```bash
systemctl stop velojol-gunicorn.service
cp /opt/open-velojol/current/instance/velojol.db \
  /opt/open-velojol/current/instance/velojol.db.before-restore.$(date +"%Y%m%d-%H%M%S")
```

Then copy the restored database into:

```text
/opt/open-velojol/current/instance/velojol.db
```

and restore uploads into:

```text
/opt/open-velojol/current/app/static/uploads
```

Finally:

```bash
systemctl start velojol-gunicorn.service
systemctl status velojol-gunicorn.service --no-pager -l
```
