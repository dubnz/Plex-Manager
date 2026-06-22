# Plex Manager

Plex Manager is a self-hosted media library operations dashboard for auditing a Plex library and planning safe cleanup actions across Plex, Tautulli, Sonarr, Radarr, and Seerr.

The current build is intentionally non-destructive. It supports local cache data, filtering, batch selection, CSV export, and delete dry-run previews. Real destructive actions remain blocked until authenticated read checks and explicit confirmation flows are implemented.

## Deploy on Proxmox

Run this on the Proxmox host as `root`:

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/dubnz/Plex-Manager/master/scripts/proxmox-create-lxc.sh)"
```

Then enter the created container and configure credentials:

```bash
pct enter <CTID>
nano /etc/plex-manager.env
systemctl start plex-manager
systemctl status plex-manager --no-pager
```

Open:

```text
http://<lxc-ip>:8000
```

See [DEPLOY.md](DEPLOY.md) for advanced and unattended install options.

## Local Development

Backend:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
PLEX_MANAGER_DEMO_MODE=true DB_PATH=data/demo-runtime.db \
  .venv/bin/python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Frontend:

```bash
npm --prefix frontend install
npm --prefix frontend run dev
```

Tests:

```bash
.venv/bin/python -m pytest backend/tests
npm --prefix frontend run test -- --run
npm --prefix frontend run build
```

## Public Repository Safety

Do not commit real `.env` files, SQLite databases, API keys, Plex tokens, or Proxmox host secrets. This repository includes only placeholder values in `.env.example`.

