#!/usr/bin/env bash
# Bitwarden-driven multi-account OCI legacy ARM resize orchestrator.
#
# Usage:
#   ./bw_oci_resize_all.sh --dry-run --start-account armandfcrouch
#   ./bw_oci_resize_all.sh --start-account armandfcrouch --accounts armandfcrouch
#   ./bw_oci_resize_all.sh
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

require_cmd() {
    local cmd=$1 hint=$2
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "Error: '$cmd' not found. $hint" >&2
        exit 1
    fi
}

if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -e .

if [ -n "${BW_NODE_BIN:-}" ]; then
    export PATH="${BW_NODE_BIN}:${PATH:-}"
fi

export PATH="$SCRIPT_DIR/.venv/bin:${PATH:-}"

require_cmd python3 "Install Python 3.11+."
require_cmd jq "Install jq for JSON processing."

DEFAULT_ITEMS="${BW_ITEMS_FILE:-$SCRIPT_DIR/.bw-items.json}"
HAS_OFFLINE_ITEMS=false
if [ -f "$DEFAULT_ITEMS" ] && [ -s "$DEFAULT_ITEMS" ]; then
    HAS_OFFLINE_ITEMS=true
fi

if [ "$HAS_OFFLINE_ITEMS" = false ]; then
    require_cmd bw "Install Bitwarden CLI: npm i -g @bitwarden/cli"
fi

require_cmd oci "Install OCI CLI: pip install oci-cli (in venv) or bash setup_oci_terraform.sh."

if [ -z "${BW_SESSION:-}" ] && [ -z "${BW_SESSION_FILE:-}" ]; then
    default_session_file="${HOME}/.cache/cloudbooter/bw-session"
    if [ -f "$default_session_file" ] && [ -s "$default_session_file" ]; then
        export BW_SESSION_FILE="$default_session_file"
    elif [ -f "$default_session_file" ] && [ ! -s "$default_session_file" ]; then
        echo "Warning: $default_session_file exists but is empty — re-run unlock:" >&2
        echo "  bw unlock --raw > ~/.cache/cloudbooter/bw-session && chmod 600 ~/.cache/cloudbooter/bw-session" >&2
    fi
fi

if [ -z "${BW_SESSION:-}" ] && [ -z "${BW_SESSION_FILE:-}" ] && [ "$HAS_OFFLINE_ITEMS" = false ]; then
    echo "Error: Bitwarden vault is locked and no offline items file found." >&2
    echo "Unlock vault:" >&2
    echo "  mkdir -p ~/.cache/cloudbooter && bw unlock --raw > ~/.cache/cloudbooter/bw-session && chmod 600 ~/.cache/cloudbooter/bw-session" >&2
    echo "Or export offline items:" >&2
    echo "  ./export_bw_items.sh" >&2
    exit 1
fi

exec python -m cloudbooter.cli bw-resize-all "$@"
