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

## 2026-06-22

Task: Prepare public GitHub repository publishing.

Status: In progress.

Completed:

- Scanned the working tree for `.env` files, SQLite databases, private keys, and common secret/token patterns.
- Added README with public install instructions and a reminder not to commit real credentials.
- Updated deployment docs and Proxmox host installer defaults to use `https://github.com/dubnz/Plex-Manager`.
- Created public GitHub repository `dubnz/Plex-Manager` and configured it as `origin`.

Public-safety note:

- No real credentials, databases, `.env`, or private key files were found. The only secret-related hits are placeholders in `.env.example`, demo values in config, and code identifiers.

Verification:

- `bash -n scripts/proxmox-create-lxc.sh && bash -n scripts/install-lxc.sh`: passed.
- `scripts/proxmox-create-lxc.sh --help`: passed.
- `.venv/bin/python -m pytest backend/tests`: 5 passed.
- `npm --prefix frontend run test -- --run`: 3 passed.
- `npm --prefix frontend run build`: passed.

## 2026-06-24

Task: Diagnose CT 100 web UI and make Plex Manager configurable from the browser.

Status: Web UI is running on CT 100; waiting on real service credentials for final connection validation.

Completed:

- SSH to Proxmox works via the `proxmox` alias.
- CT 100 is running as `plex-manager` at `192.168.158.160`.
- Root cause for the browser not loading was that `plex-manager.service` was enabled but inactive and had never logged a startup attempt.
- Started and enabled the service path in CT 100; app now listens on `0.0.0.0:8000`.
- Added web Settings for Plex, Tautulli, Sonarr, Radarr, and Seerr URLs/keys.
- Added write-only secret handling: config API never returns tokens/API keys.
- Added runtime config persistence at `/var/lib/plex-manager/config.json`.
- Added read-only connection validation from the UI.
- Added a real Sync button flow that blocks with a clear Plex-token message until credentials are configured.
- Deployed latest `master` to CT 100 and rebuilt frontend assets there.

Verification:

- `curl http://192.168.158.160:8000/api/status`: returns service status with missing placeholders.
- `curl http://192.168.158.160:8000/api/config`: returns non-secret config metadata.
- `POST /api/config/validate`: returns five missing credential statuses with no network calls while placeholders are present.
- `POST /api/sync/run`: returns `Enter a real Plex token before running sync.`
- Playwright against `http://192.168.158.160:8000`: Movies view loads, Settings view has 13 config fields, validation panel shows five missing credentials, Sync displays the Plex-token blocker.
- CT 100 repo is clean at `9861cf8`; local and GitHub `master` match.

Next step:

- Open `http://192.168.158.160:8000`, enter real service URLs/API keys in Settings, run Test connections, then run Sync.
