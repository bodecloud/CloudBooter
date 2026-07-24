#!/usr/bin/env bash
# Export decrypted Bitwarden items for offline orchestrator use.
# Run once in an unlocked terminal:
#   ./export_bw_items.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="${BW_ITEMS_FILE:-$SCRIPT_DIR/.bw-items.json}"

export PATH="${BW_NODE_BIN:+${BW_NODE_BIN}:}${PATH:-}"
require_cmd() { command -v "$1" >/dev/null 2>&1 || { echo "Missing: $1" >&2; exit 1; }; }
require_cmd bw

if [ -z "${BW_SESSION:-}" ] && [ -f "${HOME}/.cache/cloudbooter/bw-session" ]; then
    export BW_SESSION_FILE="${HOME}/.cache/cloudbooter/bw-session"
fi

if [ -z "${BW_SESSION:-}" ] && [ -z "${BW_SESSION_FILE:-}" ]; then
    echo "Unlock vault first:" >&2
    echo "  mkdir -p ~/.cache/cloudbooter" >&2
    echo "  bw unlock --raw > ~/.cache/cloudbooter/bw-session && chmod 600 ~/.cache/cloudbooter/bw-session" >&2
    exit 1
fi

bw list items > "$OUT"
chmod 600 "$OUT"
echo "Exported $(python3 -c "import json; print(len(json.load(open('$OUT'))))") items to $OUT"
