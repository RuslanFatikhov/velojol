#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="/opt/open-velojol"
CURRENT_LINK="$APP_ROOT/current"
SHARED_DIR="$APP_ROOT/shared"
ENV_FILE="$APP_ROOT/.env"
SHARED_ENV_FILE="$SHARED_DIR/.env"
VENV_PATH="$APP_ROOT/open-velojol-env"
SERVICE_NAME="velojol-gunicorn.service"

echo "[runtime] Checking server layout"
mkdir -p "$SHARED_DIR"

if [ -f "$ENV_FILE" ]; then
    ln -sfn "$ENV_FILE" "$SHARED_ENV_FILE"
    echo "[runtime] Linked $SHARED_ENV_FILE -> $ENV_FILE"
else
    echo "[runtime] WARNING: $ENV_FILE not found"
fi

ln -sfn "$APP_ROOT" "$CURRENT_LINK"
echo "[runtime] Linked $CURRENT_LINK -> $APP_ROOT"

if [ -x "$VENV_PATH/bin/python" ]; then
    PY_INFO="$(file "$VENV_PATH/bin/python" || true)"
    if printf '%s' "$PY_INFO" | grep -q 'Mach-O'; then
        echo "[runtime] Removing incompatible virtualenv at $VENV_PATH"
        rm -rf "$VENV_PATH"
    fi
fi

if [ ! -x "$VENV_PATH/bin/python" ]; then
    echo "[runtime] Creating Linux virtualenv at $VENV_PATH"
    python3 -m venv "$VENV_PATH"
fi

echo "[runtime] Installing Python dependencies"
"$VENV_PATH/bin/pip" install --upgrade pip
"$VENV_PATH/bin/pip" install --no-cache-dir -r "$APP_ROOT/requirements.txt"

echo "[runtime] Verifying Flask runtime"
"$VENV_PATH/bin/python" -c "import flask; import flask.debughelpers; print(flask.__version__)"

echo "[runtime] Restarting $SERVICE_NAME"
systemctl restart "$SERVICE_NAME"
systemctl status "$SERVICE_NAME" --no-pager -l
