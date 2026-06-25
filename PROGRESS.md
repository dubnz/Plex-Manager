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

Status: Web UI is running on CT 100 with real services configured and validated.

Completed:

- SSH to Proxmox works via the `proxmox` alias.
- CT 100 is running as `plex-manager` at `<lxc-ip>`.
- Root cause for the browser not loading was that `plex-manager.service` was enabled but inactive and had never logged a startup attempt.
- Started and enabled the service path in CT 100; app now listens on `0.0.0.0:8000`.
- Added web Settings for Plex, Tautulli, Sonarr, Radarr, and Seerr URLs/keys.
- Added write-only secret handling: config API never returns tokens/API keys.
- Added runtime config persistence at `/var/lib/plex-manager/config.json`.
- Added read-only connection validation from the UI.
- Added a real Sync button flow that blocks with a clear Plex-token message until credentials are configured.
- Deployed latest `master` to CT 100 and rebuilt frontend assets there.
- Loaded real service settings into `/var/lib/plex-manager/config.json` without committing or printing secrets.
- Discovered the exact selected Plex sections as `Movies` and `TV`.
- Updated the frontend to use configured Plex library names instead of the previous hard-coded `Movies`/`TV Shows` tabs.
- Added optional legacy Overseerr request-source configuration for read-only requester history.
- Enriched sync data from Tautulli, Radarr, Sonarr, Plex, current Jellyseerr, and legacy Overseerr.
- Made the media table horizontally scrollable on desktop so Status and Size remain reachable.

Verification:

- `curl http://<lxc-ip>:8000/api/status`: returns `demo_mode=false` and selected libraries `Movies`, `TV`.
- `curl http://<lxc-ip>:8000/api/config`: returns non-secret config metadata.
- `POST /api/config/validate`: returns OK for Plex, Tautulli, Sonarr, Radarr, Seerr, and Legacy Overseerr.
- `POST /api/sync/run`: synced 856 Plex items from selected libraries with no warnings.
- `GET /api/media?library=Movies`: returns 733 rows; 733 have size, 190 have play/history fields, 726 have requester data.
- `GET /api/media?library=TV`: returns 123 rows; 114 have Sonarr size data, 57 have play/history fields, 108 have requester data.
- Browser verification against `http://<lxc-ip>:8000`: page title is `Plex Manager`; nav shows `Movies`, `TV`, and `Settings`; Movies and TV tables include Plays, Last played, Requested by, Watched by, Status, and Size columns; table overflow is horizontally scrollable; Settings loads six stored-key states; Test connections returns six OK rows; console warnings/errors are empty.
- CT 100 repo was fast-forwarded to `bb26ffb`; local and GitHub `master` match.

Next step:

- Continue feature work from the verified LXC deployment, starting with safer cleanup/delete workflows and any deeper per-user/per-episode history views needed beyond the current aggregate table.

## 2026-06-25

Task: Improve column enrichment and legacy request history matching.

Status: Deployed to CT 100 and synced.

Completed:

- Inspected CT 100 live cache through Proxmox. Current cache has size for 733/733 Movies and 114/123 TV rows, requester data for 726/733 Movies and 108/123 TV rows, and play history for the rows present in Tautulli history.
- Hardened Plex parsing to capture nested media part sizes, Plex GUIDs, TMDB/TVDB/IMDB IDs, Plex view counts, and Plex last-viewed timestamps.
- Changed Radarr/Sonarr matching from title/year only to external-ID-first matching with unique title and alternate-title fallback.
- Changed current Seerr plus legacy Overseerr requester matching to use Plex rating key, Radarr/Sonarr ID, TMDB ID, TVDB ID, and IMDB ID.
- Added Plex play-count/last-played fallback when Tautulli history has no row for an item.

Verification:

- `.venv/bin/python -m pytest backend/tests`: 16 passed.
- `npm --prefix frontend run test -- --run`: 5 passed.
- `npm --prefix frontend run build`: passed.
- `bash -n scripts/install-lxc.sh`: passed.
- `bash -n scripts/proxmox-create-lxc.sh`: passed.
- CT 100 deployed commit `cf28859` and `plex-manager.service` restarted successfully.
- `POST /api/config/validate`: returns OK for Plex, Tautulli, Sonarr, Radarr, Seerr, and Legacy Overseerr.
- `POST /api/sync/run`: synced 856 Plex items from selected libraries with no warnings.
- Post-sync Movies: 733/733 have size, 733/733 have manager/status links, 726/733 have requester data, 214/733 have play counts, 216/733 have last-played data, and 190/733 have watched-by data.
- Post-sync TV: 118/123 have size, 118/123 have manager/status links, 108/123 have requester data, 63/123 have play counts, 60/123 have last-played data, and 57/123 have watched-by data.
