# Research Log

Date: 2026-06-22

## API references

- Plex official API reference for library sections: https://developer.plex.tv/docs/api-reference/library/get-all-libraries
- Tautulli official GitHub wiki API reference: https://github.com/Tautulli/Tautulli/wiki/Tautulli-API-Reference
- Sonarr official API docs: https://sonarr.tv/docs/api/
- Radarr official API docs: https://radarr.video/docs/api/
- Seerr API docs: https://docs.seerr.dev/api/seerr-api/
- Overseerr API docs: https://api-docs.overseerr.dev/

## Deployment references

- Proxmox `pct` manual: https://pve.proxmox.com/pve-docs/pct.1.html
- Proxmox Linux Container docs: https://pve.proxmox.com/wiki/Linux_Container
- Proxmox VE Helper-Scripts repository: https://github.com/community-scripts/ProxmoxVE
- NodeSource Node.js binary distributions: https://github.com/nodesource/distributions

## Notes

- Only read-only API operations and dry-run planning are implemented in this slice.
- Real Seerr unavailable/delete operations remain intentionally unimplemented until `SEERR_KIND` is explicit and a successful authenticated read is verified.
- Deployment is native LXC plus `systemd`, not Docker-in-LXC. Proxmox host commands in DEPLOY.md are intentionally conservative and must be checked on the target host before use.
