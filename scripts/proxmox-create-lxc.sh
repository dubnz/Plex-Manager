#!/usr/bin/env bash
set -Eeuo pipefail

# Plex Manager native LXC creator for Proxmox VE.
# Inspired by the Community Scripts flow: run on the Proxmox host, choose default
# or advanced settings, create an LXC, then install the app inside it.

APP="Plex Manager"
APP_SLUG="plex-manager"
APP_DIR="${APP_DIR:-/opt/plex-manager}"
REPO_URL="${REPO_URL:-}"
DEBIAN_VERSION="${DEBIAN_VERSION:-12}"
LOG="/tmp/${APP_SLUG}-create-$(date +%Y%m%d-%H%M%S).log"

var_unattended="${var_unattended:-no}"
var_setup="${var_setup:-default}"
var_ctid="${var_ctid:-}"
var_hostname="${var_hostname:-plex-manager}"
var_cpu="${var_cpu:-2}"
var_ram="${var_ram:-2048}"
var_swap="${var_swap:-512}"
var_disk="${var_disk:-8}"
var_storage="${var_storage:-}"
var_template_storage="${var_template_storage:-}"
var_bridge="${var_bridge:-}"
var_ip="${var_ip:-dhcp}"
var_gateway="${var_gateway:-}"
var_unprivileged="${var_unprivileged:-1}"
var_onboot="${var_onboot:-1}"

exec > >(tee -a "$LOG") 2>&1

RED="\033[31m"
GREEN="\033[32m"
YELLOW="\033[33m"
BLUE="\033[34m"
BOLD="\033[1m"
CLEAR="\033[0m"

msg() { echo -e "${BLUE}==>${CLEAR} $*"; }
ok() { echo -e "${GREEN}✓${CLEAR} $*"; }
warn() { echo -e "${YELLOW}!${CLEAR} $*"; }
die() { echo -e "${RED}✗${CLEAR} $*" >&2; exit 1; }

on_error() {
  local exit_code=$?
  echo -e "${RED}Install failed.${CLEAR} Review log: $LOG" >&2
  exit "$exit_code"
}
trap on_error ERR

shell_quote() {
  printf "'%s'" "$(printf "%s" "$1" | sed "s/'/'\\\\''/g")"
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"
}

is_yes() {
  [[ "$1" =~ ^([yY][eE][sS]|[yY]|1|true)$ ]]
}

prompt() {
  local label="$1"
  local default="$2"
  local var_name="$3"
  local value

  if is_yes "$var_unattended"; then
    printf -v "$var_name" "%s" "$default"
    return
  fi

  read -r -p "$label [$default]: " value
  printf -v "$var_name" "%s" "${value:-$default}"
}

choose_from_list() {
  local label="$1"
  local default="$2"
  local var_name="$3"
  shift 3
  local options=("$@")
  local value

  [[ "${#options[@]}" -gt 0 ]] || die "No options available for $label"

  if is_yes "$var_unattended"; then
    printf -v "$var_name" "%s" "${default:-${options[0]}}"
    return
  fi

  echo "$label"
  local i
  for i in "${!options[@]}"; do
    printf "  %d) %s\n" "$((i + 1))" "${options[$i]}"
  done
  read -r -p "Choose [${default:-${options[0]}}]: " value

  if [[ -z "$value" ]]; then
    printf -v "$var_name" "%s" "${default:-${options[0]}}"
  elif [[ "$value" =~ ^[0-9]+$ && "$value" -ge 1 && "$value" -le "${#options[@]}" ]]; then
    printf -v "$var_name" "%s" "${options[$((value - 1))]}"
  else
    printf -v "$var_name" "%s" "$value"
  fi
}

next_ctid() {
  pvesh get /cluster/nextid 2>/dev/null || echo 100
}

ctid_available() {
  local ctid="$1"
  [[ "$ctid" =~ ^[0-9]+$ ]] || return 1
  [[ ! -f "/etc/pve/lxc/${ctid}.conf" && ! -f "/etc/pve/qemu-server/${ctid}.conf" ]] || return 1
  ! pct status "$ctid" >/dev/null 2>&1
}

default_bridge() {
  if ip link show vmbr0 >/dev/null 2>&1; then
    echo "vmbr0"
    return
  fi
  ip -o link show type bridge 2>/dev/null | awk -F': ' '{print $2}' | head -n1
}

storage_list() {
  local content="$1"
  pvesm status -content "$content" 2>/dev/null | awk 'NR > 1 {print $1}'
}

select_or_default_storage() {
  local content="$1"
  local default="$2"
  local var_name="$3"
  local -a stores
  mapfile -t stores < <(storage_list "$content")
  [[ "${#stores[@]}" -gt 0 ]] || die "No Proxmox storage supports content type '$content'"

  if [[ -n "$default" ]]; then
    printf -v "$var_name" "%s" "$default"
  elif [[ "${#stores[@]}" -eq 1 ]]; then
    printf -v "$var_name" "%s" "${stores[0]}"
  else
    choose_from_list "Select storage for $content:" "${stores[0]}" "$var_name" "${stores[@]}"
  fi
}

ensure_template() {
  local storage="$1"
  local template

  msg "Refreshing Proxmox template list"
  pveam update >/dev/null

  template="$(
    pveam available --section system |
      awk -v pattern="debian-${DEBIAN_VERSION}-standard" '$2 ~ pattern && $2 ~ /amd64/ {print $2}' |
      sort -V |
      tail -n1
  )"

  [[ -n "$template" ]] || die "Could not find a Debian ${DEBIAN_VERSION} amd64 standard template via pveam."

  if ! pveam list "$storage" | awk '{print $1}' | grep -q "vztmpl/${template}$"; then
    msg "Downloading template $template to $storage"
    pveam download "$storage" "$template"
  else
    ok "Template already present: $storage:vztmpl/$template"
  fi

  echo "$storage:vztmpl/$template"
}

local_source_dir() {
  local script_dir source_dir
  script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
  source_dir="$(cd -- "$script_dir/.." && pwd)"

  if [[ -f "$source_dir/requirements.txt" && -f "$source_dir/frontend/package.json" && -f "$source_dir/scripts/install-lxc.sh" ]]; then
    echo "$source_dir"
  fi
}

copy_local_source_into_ct() {
  local source_dir="$1"
  local archive="/tmp/${APP_SLUG}-source-${CTID}.tar.gz"

  msg "Copying local source from $source_dir into CT $CTID"
  tar -C "$source_dir" \
    --exclude=".git" \
    --exclude=".venv" \
    --exclude="node_modules" \
    --exclude="frontend/node_modules" \
    --exclude="frontend/dist" \
    --exclude="data/*.db" \
    --exclude=".pytest_cache" \
    --exclude=".ruff_cache" \
    -czf "$archive" .

  pct exec "$CTID" -- mkdir -p "$APP_DIR"
  pct push "$CTID" "$archive" /tmp/plex-manager-source.tar.gz >/dev/null
  pct exec "$CTID" -- bash -lc "rm -rf $(shell_quote "$APP_DIR")/* && tar -xzf /tmp/plex-manager-source.tar.gz -C $(shell_quote "$APP_DIR")"
  rm -f "$archive"
}

install_from_repo_inside_ct() {
  local repo_q app_q
  repo_q="$(shell_quote "$REPO_URL")"
  app_q="$(shell_quote "$APP_DIR")"

  msg "Cloning $REPO_URL inside CT $CTID"
  pct exec "$CTID" -- bash -lc "apt-get update && apt-get install -y ca-certificates git curl && rm -rf $app_q && git clone $repo_q $app_q"
}

run_inner_installer() {
  local app_q
  app_q="$(shell_quote "$APP_DIR")"
  msg "Running native Plex Manager installer inside CT $CTID"
  pct exec "$CTID" -- bash -lc "chmod +x $app_q/scripts/install-lxc.sh && APP_DIR=$app_q $app_q/scripts/install-lxc.sh"
}

wait_for_ct() {
  msg "Waiting for CT $CTID to become ready"
  local attempt
  for attempt in {1..30}; do
    if pct exec "$CTID" -- bash -lc "test -f /etc/os-release" >/dev/null 2>&1; then
      ok "CT is responding"
      return
    fi
    sleep 2
  done
  die "Timed out waiting for CT $CTID"
}

ct_ip() {
  pct exec "$CTID" -- bash -lc "hostname -I | awk '{print \$1}'" 2>/dev/null || true
}

header() {
  clear || true
  echo -e "${BOLD}${APP} Proxmox LXC Installer${CLEAR}"
  echo "Creates a native LXC service. Docker is not used."
  echo
}

usage() {
  cat <<EOF
Usage:
  ./scripts/proxmox-create-lxc.sh

Run from a checked-out repo on the Proxmox host, or set REPO_URL when running
from a raw one-liner.

Common variables:
  REPO_URL=<repo-url>             Clone this repo inside the CT instead of copying local source
  var_setup=advanced              Prompt for CTID, CPU, RAM, disk, bridge, and IP settings
  var_unattended=yes              Use defaults or supplied var_* values without prompts
  var_ctid=120                    Container ID
  var_hostname=plex-manager       Container hostname
  var_cpu=2                       CPU cores
  var_ram=2048                    Memory in MB
  var_disk=8                      Root disk in GB
  var_storage=local-lvm           Root filesystem storage
  var_template_storage=local      Template storage
  var_bridge=vmbr0                Proxmox bridge
  var_ip=dhcp                     DHCP or static CIDR, e.g. 192.168.1.50/24
  var_gateway=192.168.1.1         Gateway when using static IPv4
EOF
}

preflight() {
  [[ "$(id -u)" -eq 0 ]] || die "Run this script as root on the Proxmox host."
  need_cmd pct
  need_cmd pvesh
  need_cmd pvesm
  need_cmd pveam
  need_cmd tar
  need_cmd ip
}

collect_settings() {
  local suggested_ctid bridge source_dir

  suggested_ctid="${var_ctid:-$(next_ctid)}"
  bridge="${var_bridge:-$(default_bridge)}"
  source_dir="$(local_source_dir || true)"

  if [[ -z "$REPO_URL" && -z "$source_dir" ]]; then
    die "Set REPO_URL=https://... or run this script from a checked-out Plex Manager repo."
  fi

  if ! is_yes "$var_unattended"; then
    read -r -p "Use default settings? [Y/n]: " reply
    if [[ "$reply" =~ ^[nN] ]]; then
      var_setup="advanced"
    else
      var_setup="default"
    fi
  fi

  if [[ "$var_setup" == "advanced" ]]; then
    prompt "Container ID" "$suggested_ctid" CTID
    prompt "Hostname" "$var_hostname" HOSTNAME
    prompt "CPU cores" "$var_cpu" CORES
    prompt "Memory MB" "$var_ram" RAM
    prompt "Swap MB" "$var_swap" SWAP
    prompt "Root disk GB" "$var_disk" DISK
    prompt "Network bridge" "${bridge:-vmbr0}" BRIDGE
    prompt "IPv4 CIDR or dhcp" "$var_ip" IP_CONFIG
    if [[ "$IP_CONFIG" != "dhcp" ]]; then
      prompt "Gateway IPv4" "$var_gateway" GATEWAY
    else
      GATEWAY=""
    fi
  else
    CTID="$suggested_ctid"
    HOSTNAME="$var_hostname"
    CORES="$var_cpu"
    RAM="$var_ram"
    SWAP="$var_swap"
    DISK="$var_disk"
    BRIDGE="${bridge:-vmbr0}"
    IP_CONFIG="$var_ip"
    GATEWAY="$var_gateway"
  fi

  ctid_available "$CTID" || die "CTID $CTID is already in use or invalid."

  select_or_default_storage rootdir "$var_storage" STORAGE
  select_or_default_storage vztmpl "$var_template_storage" TEMPLATE_STORAGE

  [[ -n "$BRIDGE" ]] || die "No network bridge found. Set var_bridge=vmbr0 or choose advanced setup."
}

create_container() {
  local template_ref net0

  template_ref="$(ensure_template "$TEMPLATE_STORAGE" | tail -n1)"
  net0="name=eth0,bridge=${BRIDGE},ip=${IP_CONFIG}"
  if [[ -n "${GATEWAY:-}" ]]; then
    net0="${net0},gw=${GATEWAY}"
  fi

  msg "Creating CT $CTID ($HOSTNAME)"
  pct create "$CTID" "$template_ref" \
    --hostname "$HOSTNAME" \
    --cores "$CORES" \
    --memory "$RAM" \
    --swap "$SWAP" \
    --rootfs "${STORAGE}:${DISK}" \
    --net0 "$net0" \
    --unprivileged "$var_unprivileged" \
    --onboot "$var_onboot" \
    --ostype debian \
    --tags "$APP_SLUG"

  ok "Created CT $CTID"
}

main() {
  if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    usage
    exit 0
  fi

  header
  preflight
  collect_settings

  echo
  msg "Configuration"
  echo "  CTID:              $CTID"
  echo "  Hostname:          $HOSTNAME"
  echo "  CPU/RAM/Disk:      ${CORES} cores / ${RAM} MB / ${DISK} GB"
  echo "  Storage:           $STORAGE"
  echo "  Template storage:  $TEMPLATE_STORAGE"
  echo "  Network:           $BRIDGE / $IP_CONFIG"
  echo "  Source:            ${REPO_URL:-local checkout}"
  echo

  if ! is_yes "$var_unattended"; then
    read -r -p "Create this LXC now? [Y/n]: " reply
    [[ "$reply" =~ ^[nN] ]] && die "Cancelled."
  fi

  create_container
  msg "Starting CT $CTID"
  pct start "$CTID"
  wait_for_ct

  if [[ -n "$REPO_URL" ]]; then
    install_from_repo_inside_ct
  else
    copy_local_source_into_ct "$(local_source_dir)"
  fi

  run_inner_installer

  local ip
  ip="$(ct_ip)"

  ok "$APP LXC created successfully"
  echo
  echo "Next steps:"
  echo "  pct enter $CTID"
  echo "  nano /etc/plex-manager.env"
  echo "  systemctl start plex-manager"
  echo "  systemctl status plex-manager --no-pager"
  echo
  echo "URL after service start:"
  echo "  http://${ip:-<lxc-ip>}:8000"
  echo
  echo "Log: $LOG"
}

main "$@"
