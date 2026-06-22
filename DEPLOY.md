# Deploy

This is the native Proxmox LXC deployment path for Plex Manager. Docker is not used.

## Shape

Plex Manager runs directly inside a Debian/Ubuntu LXC container:

- Python FastAPI backend in `/opt/plex-manager/.venv`
- Built Vite frontend in `/opt/plex-manager/frontend/dist`
- SQLite cache in `/var/lib/plex-manager/plex-manager.db`
- Environment file at `/etc/plex-manager.env`
- `systemd` service named `plex-manager`

The app listens on:

```text
http://<lxc-ip>:8000
```

## Create the LXC

On the Proxmox host, create an unprivileged Debian container. The exact storage name, bridge, template name, and CTID depend on your host.

Example:

```bash
pct create <CTID> local:vztmpl/debian-12-standard_*.tar.zst \
  --hostname plex-manager \
  --cores 2 \
  --memory 2048 \
  --swap 512 \
  --rootfs local-lvm:8 \
  --net0 name=eth0,bridge=vmbr0,ip=dhcp \
  --unprivileged 1 \
  --onboot 1

pct start <CTID>
pct enter <CTID>
```

No Docker nesting flags are required for Plex Manager.

Inside the LXC:

```bash
apt update
apt install -y ca-certificates curl git
git clone <repo-url> /opt/plex-manager
cd /opt/plex-manager
./scripts/install-lxc.sh
nano /etc/plex-manager.env
systemctl start plex-manager
systemctl status plex-manager --no-pager
```

You can also let the installer clone the repo:

```bash
REPO_URL=<repo-url> /bin/bash -c "$(curl -fsSL <raw-install-script-url>)"
```

Use that only after replacing `<raw-install-script-url>` with the actual raw URL for this repository.

## Required production checks

- `PLEX_MANAGER_DEMO_MODE=false`
- `SEERR_KIND` is set to exactly `overseerr` or `jellyseerr`
- Authenticated read-only calls succeed for Plex, Tautulli, Sonarr, Radarr, and Seerr
- Plex library discovery records exact target sections and excludes similarly named libraries
- Delete dry-runs are verified before any real destructive action is implemented or enabled

## Service commands

```bash
systemctl restart plex-manager
journalctl -u plex-manager -f
systemctl disable --now plex-manager
```

## References checked

- Proxmox `pct` manual: https://pve.proxmox.com/pve-docs/pct.1.html
- Proxmox Linux Container docs: https://pve.proxmox.com/wiki/Linux_Container
- NodeSource Node.js binary distributions: https://github.com/nodesource/distributions
