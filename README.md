# Velojol

## Map

City maps use Mapbox GL JS. Add a public token (it must start with `pk.`) to
the local `.env`:

```dotenv
MAPBOX_TOKEN=pk.your-public-token
```

Never put a secret `sk.` token into the application: browser visitors can see
the map token. For production, add `MAPBOX_TOKEN` to
`/opt/open-velojol/shared/.env` and restart `velojol-gunicorn.service`.

## Google sign-in

Create an OAuth client of type **Web application** in Google Cloud and set:

```dotenv
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=https://open.velojol.kz/auth/google/callback
```

Add the exact same `GOOGLE_REDIRECT_URI` value to the client's **Authorized
redirect URIs**. For local development, create/add a localhost callback such as
`http://localhost:5500/auth/google/callback` and use it in the local `.env`.
The redirect URI must match exactly, including scheme, host, port, and path.
On production, add these variables to `/opt/open-velojol/shared/.env` and restart
`velojol-gunicorn.service` after installing requirements and running migrations.

## Telegram sign-in

Create a Telegram bot in BotFather, open **Bot Settings → Web Login**, and add
both the production origin and callback:

```text
https://open.velojol.kz
https://open.velojol.kz/auth/telegram/callback
```

Configure the OIDC credentials in `.env`:

```dotenv
TELEGRAM_CLIENT_ID=your-bot-client-id
TELEGRAM_CLIENT_SECRET=your-client-secret
TELEGRAM_REDIRECT_URI=https://open.velojol.kz/auth/telegram/callback
```

The public login page opens Telegram in the user's browser and verifies the
returned ID token locally against Telegram's pinned public key. This avoids
requiring the application server to connect to Telegram's network. Refresh
`app/data/telegram_jwks.json` from Telegram's official JWKS endpoint when
Telegram rotates its signing key. Telegram does not provide an email in this
flow, so Telegram users are identified by the verified OIDC `sub` claim and may
have an empty email field. The public login page currently shows Telegram and
Google only; the legacy email/password form is intentionally hidden while its
backend remains available as an emergency compatibility path for existing
accounts.

On production, keep these values in `/opt/open-velojol/shared/.env`, run
`flask --app run:app db upgrade`, and restart `velojol-gunicorn.service`.

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

Create the local deploy configuration without committing credentials:

```bash
cp .deploy.env.example .deploy.env
```

Set `DEPLOY_TARGET` in `.deploy.env`, then inspect the release without changing
the server:

```bash
./deploy_velojol.sh --dry-run
```

After reviewing the dry-run, an explicitly approved deployment can be run with:

```bash
./deploy_velojol.sh --apply
```

The apply mode creates a timestamped code archive and an SQLite `.backup`
before upload. It does not use `rsync --delete`, and excludes the database,
uploads, runtime secrets, virtual environments and backup directories.

### Manual rsync reference

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

## Legacy velojol.kz migration

The original `public_html` archive can be inspected without changing the
database:

```bash
python3 scripts/import_legacy_velojol.py \
  --dry-run \
  --source-root /path/to/public_html \
  --database instance/velojol.db \
  --report /tmp/legacy-velojol-dry-run.json
```

Before applying, run the schema migration and review every `review` item in the
JSON report:

```bash
flask db upgrade
python3 scripts/import_legacy_velojol.py \
  --apply \
  --source-root /path/to/public_html \
  --database instance/velojol.db \
  --report /tmp/legacy-velojol-apply.json
```

Applied mode creates a consistent SQLite backup before any import write.
Exact legacy geometry duplicates are collapsed. Unique high-confidence OSM
matches retain their OSM identifiers, geometry, owner and moderation state
while receiving richer legacy text, quality and photos. Ambiguous or partial
matches are never written automatically.
