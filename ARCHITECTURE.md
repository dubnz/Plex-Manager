# Architecture

## Stack choice

Plex Manager is a single deployable app:

- Backend: Python FastAPI, because Python has excellent stdlib SQLite support and readable integration/test ergonomics.
- Frontend: React + Vite, because this is an operations dashboard with interactive filtering, batch selection, dry-run previews, and client-side table state.
- Local cache: SQLite, stored at `DB_PATH`, so Plex/Tautulli/Sonarr/Radarr/Seerr are synced into local storage and the UI does not hammer live APIs on every page load.
- Deployment: Docker Compose inside the LXC, because it keeps runtime dependencies and upgrades contained. The Proxmox `pct`/LXC flags still need to be re-verified against the target host before DEPLOY.md is considered final.

## Safety model

Destructive actions are not exposed as real mutations in this first slice. The app supports delete dry-runs that produce an itemized plan and require a future explicit confirm step before any Sonarr, Radarr, Seerr, Plex, or filesystem mutation can run.

## Integration boundaries

Each external system has a thin client module under `backend/app/clients`:

- `plex.py`
- `tautulli.py`
- `sonarr.py`
- `radarr.py`
- `seerr.py`

The clients share retry/backoff and request handling from `base.py`. API call sites include a source URL comment above each endpoint call, per the build-loop rule.

## Official references checked

- Plex API: https://developer.plex.tv/docs/api-reference/library/get-all-libraries
- Tautulli API reference: https://github.com/Tautulli/Tautulli/wiki/Tautulli-API-Reference
- Sonarr API docs: https://sonarr.tv/docs/api/
- Radarr API docs: https://radarr.video/docs/api/
- Seerr/Jellyseerr docs: https://docs.seerr.dev/api/seerr-api/
- Overseerr API docs: https://api-docs.overseerr.dev/
- Proxmox `pct` manual: https://pve.proxmox.com/pve-docs/pct.1.html
- Proxmox VE Helper-Scripts repository: https://github.com/community-scripts/ProxmoxVE

## Environment behavior

With `PLEX_MANAGER_DEMO_MODE=false`, startup fails fast if required credentials are missing or if `SEERR_KIND` is not exactly `overseerr` or `jellyseerr`. With `PLEX_MANAGER_DEMO_MODE=true`, the app serves representative local data for UI development only.

