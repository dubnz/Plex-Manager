#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/plex-manager}"
ENV_FILE="${ENV_FILE:-/etc/plex-manager.env}"
DATA_DIR="${DATA_DIR:-/var/lib/plex-manager}"
SERVICE_FILE="${SERVICE_FILE:-/etc/systemd/system/plex-manager.service}"
REPO_URL="${REPO_URL:-}"
NODE_MAJOR="${NODE_MAJOR:-22}"
SERVICE_USER="${SERVICE_USER:-plex-manager}"
SERVICE_PORT="${SERVICE_PORT:-8000}"

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "Run this script as root inside the LXC container." >&2
  exit 1
fi

apt-get update
apt-get install -y ca-certificates curl git python3 python3-venv python3-pip build-essential sqlite3

if ! command -v node >/dev/null 2>&1 || [[ "$(node -v | sed 's/^v//' | cut -d. -f1)" -lt 20 ]]; then
  curl -fsSL "https://deb.nodesource.com/setup_${NODE_MAJOR}.x" -o /tmp/nodesource_setup.sh
  bash /tmp/nodesource_setup.sh
  apt-get install -y nodejs
fi

if [[ -n "$REPO_URL" && ! -d "$APP_DIR/.git" && ! -f "$APP_DIR/requirements.txt" ]]; then
  git clone "$REPO_URL" "$APP_DIR"
elif [[ ! -f "$APP_DIR/requirements.txt" || ! -f "$APP_DIR/frontend/package.json" || ! -f "$APP_DIR/scripts/install-lxc.sh" ]]; then
  echo "Clone or copy the Plex Manager repo to $APP_DIR first, or rerun with REPO_URL=https://..." >&2
  exit 1
fi

cd "$APP_DIR"
if [[ -d "$APP_DIR/.git" ]]; then
  git config --global --add safe.directory "$APP_DIR" >/dev/null 2>&1 || true
  git pull --ff-only || true
fi

mkdir -p "$DATA_DIR"

if ! id -u "$SERVICE_USER" >/dev/null 2>&1; then
  useradd --system --home-dir "$APP_DIR" --shell /usr/sbin/nologin "$SERVICE_USER"
fi

python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/python" -m pip install --upgrade pip
"$APP_DIR/.venv/bin/python" -m pip install -r "$APP_DIR/requirements.txt"

npm --prefix "$APP_DIR/frontend" ci
npm --prefix "$APP_DIR/frontend" run build

if [[ ! -f "$ENV_FILE" ]]; then
  install -m 0640 -o root -g "$SERVICE_USER" "$APP_DIR/.env.example" "$ENV_FILE"
  sed -i "s#^DB_PATH=.*#DB_PATH=$DATA_DIR/plex-manager.db#" "$ENV_FILE"
  echo "Created $ENV_FILE. Fill in real credentials before starting the service."
fi

cat > "$SERVICE_FILE" <<SERVICE
[Unit]
Description=Plex Manager
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User=$SERVICE_USER
Group=$SERVICE_USER
WorkingDirectory=$APP_DIR
EnvironmentFile=$ENV_FILE
ExecStart=$APP_DIR/.venv/bin/uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port $SERVICE_PORT
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ReadWritePaths=$DATA_DIR

[Install]
WantedBy=multi-user.target
SERVICE

chown -R "$SERVICE_USER:$SERVICE_USER" "$APP_DIR" "$DATA_DIR"
chmod 0750 "$DATA_DIR"

systemctl daemon-reload
systemctl enable plex-manager.service

cat <<EOF
Plex Manager is installed as a native LXC service.

1. Edit credentials:
   nano $ENV_FILE

2. Start the app:
   systemctl start plex-manager

3. Check status:
   systemctl status plex-manager --no-pager

4. Open:
   http://$(hostname -I | awk '{print $1}'):$SERVICE_PORT
EOF
