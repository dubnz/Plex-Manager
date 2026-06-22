# Assumptions

- The workspace did not contain existing source files, so this build starts from a greenfield scaffold.
- No production API credentials are present in the workspace. Demo mode exists only to let the dashboard and dry-run logic run before credentials are configured.
- The selected Plex libraries must be discovered from the target server. The app defaults to display names `Movies` and `TV Shows` in `.env.example`, but real startup should use `GET /library/sections` and persist exact IDs/names before sync.
- Seerr is not assumed. The app requires `SEERR_KIND=overseerr` or `SEERR_KIND=jellyseerr`; real Seerr mutation work remains blocked until this is explicit.
- Native service inside a Proxmox LXC is the deployment choice. Docker is intentionally not used.
