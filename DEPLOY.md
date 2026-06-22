# Deploy

This is the initial deployment path for Plex Manager. Final Proxmox host-specific commands still need to be verified against the target Proxmox VE version before the deployment checklist is considered complete.

## Local or LXC app start

```bash
cp .env.example .env
# Edit .env with real service URLs and keys.
docker compose up -d --build
```

The app listens on:

```text
http://<lxc-ip>:8000
```

## Proxmox LXC notes

Use a Debian LXC with nesting enabled for Docker-in-LXC. Confirm the exact `pct create` feature flags on the target Proxmox VE host before running production commands.

Inside the LXC:

```bash
apt update
apt install -y ca-certificates curl git
curl -fsSL https://get.docker.com | sh
git clone <repo-url> /opt/plex-manager
cd /opt/plex-manager
cp .env.example .env
$EDITOR .env
docker compose up -d --build
```

## Required production checks

- `PLEX_MANAGER_DEMO_MODE=false`
- `SEERR_KIND` is set to exactly `overseerr` or `jellyseerr`
- Authenticated read-only calls succeed for Plex, Tautulli, Sonarr, Radarr, and Seerr
- Plex library discovery records exact target sections and excludes similarly named libraries
- Delete dry-runs are verified before any real destructive action is implemented or enabled

