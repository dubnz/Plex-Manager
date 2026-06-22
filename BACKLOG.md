# Backlog

## Phase 0 - Discovery

- [ ] Confirm exact Plex library section IDs/names via `GET /library/sections` on the target Plex server; record only "Movies" and "TV Shows" or actual matching names, explicitly excluding Movies2/TV2/others.
- [ ] Inventory available auth: Plex token, Tautulli API key, Sonarr API key, Radarr API key, Seerr API key.
- [ ] Determine whether Seerr is Overseerr or Jellyseerr and whether the old Overseerr LXC is queryable via HTTP or only via SQLite DB.
- [x] Decide deployment target shape: native app inside a Proxmox LXC with a `systemd` service.

## Phase 1 - API Clients

- [x] Create client module boundaries with auth, typed responses, and retry/backoff scaffolding.
- [x] Plex client: list libraries and list items per library.
- [x] Tautulli client: read history via command API.
- [x] Sonarr client: list series and guarded delete method.
- [x] Radarr client: list movies and guarded delete method.
- [x] Seerr client: list requests for the configured Seerr service.
- [ ] Overseerr legacy fallback: read-only SQLite extraction script if API path is dead.

## Phase 2 - Data Model and Sync

- [x] Local schema for media items and stats in SQLite.
- [x] Seeded demo dataset for frontend and dry-run verification.
- [ ] Background interval sync merging Plex + Tautulli + Sonarr/Radarr + Seerr into local DB.
- [ ] Sync error handling for partial failures.

## Phase 3 - Frontend

- [x] Movies and TV Shows tabs.
- [x] Sortable/filterable table with oldest-added-first default.
- [x] Batch select and action bar.
- [x] Delete dry-run preview.
- [x] Quick filters for never watched and watched by no one.
- [x] Export CSV action.
- [ ] Confirmation modal for real destructive action.

## Phase 4 - Destructive Action Orchestration

- [x] Dry-run delete plan builder.
- [ ] Real delete orchestration after authenticated reads and explicit confirmation are verified.
- [ ] Partial-failure handling for real mutation flow.

## Phase 5 - Packaging and Deploy

- [x] Community Scripts-style Proxmox host installer that creates the LXC and invokes the in-container install.
- [x] Native LXC install script with Python venv, Vite build, SQLite data directory, and `systemd` service.
- [x] `.env.example` documenting required variables.
- [x] Initial LXC install script.
- [x] DEPLOY.md updated for native Proxmox LXC deployment without Docker.
