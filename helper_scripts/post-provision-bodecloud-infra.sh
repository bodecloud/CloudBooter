#!/usr/bin/env bash
# Post-provision pipeline for bodecloud-infra on Oracle VPS nodes.
# Invoked by CloudBooter after instance launch/recreate, or manually via SSH.
#
# Usage (on the target VPS):
#   curl -fsSL https://raw.githubusercontent.com/bodecloud/bodecloud-infra/main/scripts/hands-off-bootstrap.sh | \
#     sudo TS_HOSTNAME=vractormania DOMAIN=bolabaden.org \
#     FAILOVER_MAIN_HOST=micklethefickle \
#     CLOUDFLARE_API_TOKEN=... TAILSCALE_AUTH_KEY=... bash
#
# Or after clone:
#   sudo bash /home/ubuntu/bodecloud-infra/scripts/hands-off-bootstrap.sh
set -euo pipefail

ROOT="${ROOT_DIR:-/home/ubuntu/bodecloud-infra}"
REPO_URL="${BODECLOUD_INFRA_REPO:-https://github.com/bodecloud/bodecloud-infra.git}"
EXEC="${ROOT}/scripts/hands-off-bootstrap.sh"

log() { echo "[post-provision-bodecloud-infra] $*"; }

wait_for_host() {
  local i
  for ((i = 1; i <= 30; i++)); do
    command -v docker >/dev/null 2>&1 && return 0
    [[ -f /var/log/cloud-init-complete.log ]] && return 0
    sleep 5
  done
  log "WARN: host readiness timeout; continuing"
}

wait_for_host

if [[ ! -x "$EXEC" ]]; then
  log "Cloning ${REPO_URL} → ${ROOT}"
  sudo mkdir -p "$(dirname "$ROOT")"
  sudo git clone "$REPO_URL" "$ROOT"
  sudo chown -R "${SUDO_USER:-ubuntu}:${SUDO_USER:-ubuntu}" "$ROOT"
fi

export ROOT_DIR="$ROOT"
exec bash "$EXEC" "$@"
