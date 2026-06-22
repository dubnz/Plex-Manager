# Progress

## 2026-06-22

Task: Bootstrap Plex Manager from the agentic build-loop specification.

Status: First non-destructive slice implemented.

Completed:

- Created architecture, backlog, progress, assumptions, research, and deploy docs.
- Chose FastAPI + React/Vite + SQLite + native `systemd` deployment inside a Proxmox LXC.
- Added thin API client modules with retry/backoff and official-source comments.
- Added local SQLite schema plus demo seed data.
- Added media list and dry-run delete API endpoints.
- Added dashboard UI with Movies/TV tabs, filters, batch selection, CSV export, and delete preview.
- Added native LXC install script that builds the frontend, installs the backend venv, writes `/etc/plex-manager.env`, and creates a `systemd` service.
- Verified backend tests, frontend tests, frontend build, desktop UI load, dry-run preview interaction, and mobile layout.

Blockers:

- No target `.env` or reachable Plex/Tautulli/Sonarr/Radarr/Seerr services are available in this workspace, so Phase 0 live auth and library-section discovery cannot be completed here.
- `SEERR_KIND` is intentionally not assumed. The app requires `overseerr` or `jellyseerr` before non-demo startup.

Next step:

- Fill `.env`, run authenticated read-only discovery, record the exact Plex library names/IDs, and then implement the background sync merge.

Verification:

- `.venv/bin/python -m pytest backend/tests`: 5 passed.
- `npm --prefix frontend run test -- --run`: 3 passed.
- `npm --prefix frontend run build`: passed.
- Direct API probe for `/api/media?library=Movies`: returned 2 backend-seeded demo rows.
- Playwright fallback was used because the in-app browser control was not available. Desktop 1440x980 loaded the Movies table from the backend and produced a delete dry-run preview after selecting a row.
- Mobile 390x900 had no page-level horizontal overflow; the table scrolls within its panel.

## 2026-06-22

Task: Switch deployment from Docker-in-LXC to native LXC.

Status: Implemented.

Completed:

- Added `scripts/proxmox-create-lxc.sh`, a Proxmox-host installer with default/advanced/unattended modes, CTID/storage/bridge handling, Debian template download, LXC creation, and in-container install.
- Removed Docker as the default runtime path.
- Updated `.env.example` to store SQLite data under `/var/lib/plex-manager`.
- Reworked `scripts/install-lxc.sh` to install Node.js 22, Python venv dependencies, built frontend assets, `/etc/plex-manager.env`, and a `plex-manager.service` unit.
- Updated deployment docs and backlog to describe a native Proxmox LXC service.
- Verified installer shell syntax, backend tests, frontend tests, and frontend build.

Next step:

- Run `scripts/proxmox-create-lxc.sh` on the Proxmox host, fill `/etc/plex-manager.env` inside the created LXC, then start `plex-manager.service`.

Verification:

- `bash -n scripts/proxmox-create-lxc.sh`: passed.
- `bash -n scripts/install-lxc.sh`: passed.
- `scripts/proxmox-create-lxc.sh --help`: passed.
- `.venv/bin/python -m pytest backend/tests`: 5 passed.
- `npm --prefix frontend run test -- --run`: 3 passed.
- `npm --prefix frontend run build`: passed.
