#!/usr/bin/env bash
# Post-provision pipeline for bodecloud-infra on Oracle VPS nodes.
# Invoked by CloudBooter after instance launch/recreate, or manually via SSH.
#
# Flow: optional recreate/prune → clone bodecloud-infra → bootstrap → literal compose → verify → CF DNS
#
# Usage (on the target VPS):
#   sudo TS_HOSTNAME=vractormania DOMAIN=bolabaden.org \
#     FAILOVER_MAIN_HOST=micklethefickle \
#     CLOUDFLARE_API_TOKEN=... TAILSCALE_AUTH_KEY=... \
#     /path/to/post-provision-bodecloud-infra.sh
#
# From operator workstation (after cloudbooter/terraform apply):
#   ssh ubuntu@NEW_IP 'curl -fsSL ... | sudo TS_HOSTNAME=vractormania ... bash -s'
#
# Environment:
#   RECREATE_INSTANCE=true     — update Cloudflare A record after relaunch
#   MIN_FREE_GB=10             — prune Docker if free disk below threshold
#   BODECLOUD_INFRA_REPO       — default https://github.com/bodecloud/bodecloud-infra.git
#   ROOT_DIR                   — default /home/ubuntu/bodecloud-infra
#   SKIP_VERIFY=true           — skip verify-bootstrap-stack.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${ROOT_DIR:-/home/ubuntu/bodecloud-infra}"
REPO_URL="${BODECLOUD_INFRA_REPO:-https://github.com/bodecloud/bodecloud-infra.git}"
HANDOFF="${ROOT}/scripts/cloudbooter-handoff.sh"
MIN_FREE_GB="${MIN_FREE_GB:-10}"
SKIP_VERIFY="${SKIP_VERIFY:-false}"

log() { echo "[post-provision-bodecloud-infra] $*"; }

free_gb() {
  df -BG --output=avail / 2>/dev/null | tail -1 | tr -dc '0-9' || echo 0
}

wait_for_ssh_ready() {
  local max="${1:-60}"
  local i
  for ((i = 1; i <= max; i++)); do
    if command -v cloud-init >/dev/null 2>&1 && [[ -f /var/log/cloud-init-complete.log ]]; then
      return 0
    fi
    if command -v docker >/dev/null 2>&1; then
      return 0
    fi
    sleep 5
  done
  log "WARN: cloud-init readiness timeout; continuing"
}

# 1. Disk guard + Docker prune on exhausted nodes
if [[ "$(free_gb)" -lt "$MIN_FREE_GB" ]]; then
  log "Disk low ($(free_gb)GB free); pruning Docker"
  docker system prune -af --volumes 2>/dev/null || true
fi

wait_for_ssh_ready 30

# 2. Clone bodecloud-infra
if [[ ! -d "${ROOT}/.git" ]]; then
  log "Cloning ${REPO_URL} → ${ROOT}"
  sudo mkdir -p "$(dirname "$ROOT")"
  sudo git clone "$REPO_URL" "$ROOT"
  sudo chown -R "${SUDO_USER:-ubuntu}:${SUDO_USER:-ubuntu}" "$ROOT"
fi

# 3–7. Delegate to in-repo handoff (bootstrap → compose → verify → CF DNS)
if [[ -x "$HANDOFF" ]]; then
  export ROOT_DIR="$ROOT"
  if [[ "$SKIP_VERIFY" == "true" ]]; then
    # handoff always verifies; wrap with env to skip if needed in future
    log "Running cloudbooter-handoff from ${HANDOFF}"
  fi
  exec bash "$HANDOFF"
fi

log "ERROR: ${HANDOFF} not found — sync bodecloud-infra first"
exit 1
