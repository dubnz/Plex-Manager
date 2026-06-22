#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/plex-manager}"
REPO_URL="${REPO_URL:-}"

if [[ -z "$REPO_URL" ]]; then
  echo "Set REPO_URL to the Plex Manager git repository before running this script." >&2
  exit 1
fi

apt update
apt install -y ca-certificates curl git

if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sh
fi

if [[ ! -d "$APP_DIR/.git" ]]; then
  git clone "$REPO_URL" "$APP_DIR"
fi

cd "$APP_DIR"

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created $APP_DIR/.env. Fill in credentials, then rerun docker compose up -d --build." >&2
  exit 2
fi

docker compose up -d --build
echo "Plex Manager is starting. Open http://$(hostname -I | awk '{print $1}'):8000"

