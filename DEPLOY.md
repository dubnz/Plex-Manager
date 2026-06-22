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

### Option A: Community Scripts-style host installer

Run this on the Proxmox host as `root`.

From a checked-out repo:

```bash
git clone <repo-url> /root/plex-manager
cd /root/plex-manager
./scripts/proxmox-create-lxc.sh
```

One-line style, after this repo has a reachable raw URL:

```bash
REPO_URL=<repo-url> bash -c "$(curl -fsSL <raw-proxmox-create-lxc.sh-url>)"
```

Advanced mode:

```bash
var_setup=advanced ./scripts/proxmox-create-lxc.sh
```

Unattended example:

```bash
REPO_URL=<repo-url> \
var_unattended=yes \
var_ctid=120 \
var_hostname=plex-manager \
var_cpu=2 \
var_ram=2048 \
var_disk=8 \
var_storage=local-lvm \
var_template_storage=local \
var_bridge=vmbr0 \
bash -c "$(curl -fsSL <raw-proxmox-create-lxc.sh-url>)"
```

The host installer creates the LXC, starts it, installs Plex Manager inside it, enables `plex-manager.service`, and then prints the next steps. It does not start the app with placeholder credentials.

### Option B: Manual LXC creation

On the Proxmox host, create an unprivileged Debian container yourself. The exact storage name, bridge, template name, and CTID depend on your host.

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
