"""Cloudflare authentication helpers.

Supports:
  1. CLOUDFLARE_API_TOKEN env (preferred for non-interactive / Terraform)
  2. Wrangler OAuth session (interactive)
  3. Explicit token file via CLOUDFLARE_API_TOKEN_FILE

Refs:
  https://developers.cloudflare.com/fundamentals/api/get-started/create-token/
  https://developers.cloudflare.com/workers/wrangler/commands/
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path


def detect_auth_pattern() -> str:
    """Return the active auth pattern name."""
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    if token:
        return "api_token"

    token_file = os.environ.get("CLOUDFLARE_API_TOKEN_FILE", "").strip()
    if token_file and Path(token_file).exists():
        return "token_file"

    if shutil.which("wrangler") or shutil.which("npx"):
        return "wrangler"

    return "missing"


def resolve_api_token() -> str | None:
    """Resolve an API token from env or token file."""
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    if token:
        return token

    token_file = os.environ.get("CLOUDFLARE_API_TOKEN_FILE", "").strip()
    if token_file and Path(token_file).exists():
        return Path(token_file).read_text(encoding="utf-8").strip() or None

    return None


def resolve_account_id() -> str | None:
    """Resolve account ID from env."""
    account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
    return account_id or None


def setup_wrangler_interactive() -> bool:
    """Run wrangler login for interactive OAuth setup."""
    wrangler = shutil.which("wrangler")
    cmd: list[str]
    if wrangler:
        cmd = [wrangler, "login"]
    elif shutil.which("npx"):
        cmd = ["npx", "--yes", "wrangler", "login"]
    else:
        return False

    print("[cloudbooter] Running wrangler login for interactive auth…")
    r = subprocess.run(cmd, check=False)  # noqa: S603
    return r.returncode == 0


def verify_credentials(token: str | None = None, account_id: str | None = None) -> tuple[bool, str]:
    """Verify API token works via Cloudflare REST API. Returns (ok, message)."""
    token = token or resolve_api_token()
    if not token:
        return False, "No CLOUDFLARE_API_TOKEN (or token file) found"

    try:
        import requests

        headers = {"Authorization": f"Bearer {token}"}
        # Token verify endpoint
        resp = requests.get(
            "https://api.cloudflare.com/client/v4/user/tokens/verify",
            headers=headers,
            timeout=15,
        )
        data = resp.json()
        if not data.get("success"):
            return False, f"Token verify failed: {data.get('errors')}"

        status = data.get("result", {}).get("status", "unknown")
        if account_id or resolve_account_id():
            aid = account_id or resolve_account_id()
            # Soft check: list workers (or accounts) to confirm account access
            resp2 = requests.get(
                f"https://api.cloudflare.com/client/v4/accounts/{aid}/workers/scripts",
                headers=headers,
                timeout=15,
            )
            if resp2.status_code == 403:
                return False, f"Token valid but lacks Workers access on account {aid}"
            if resp2.status_code >= 400 and resp2.status_code != 404:
                # 200 empty list is fine; other errors are informative
                body = resp2.json() if resp2.headers.get("content-type", "").startswith("application/json") else {}
                if not body.get("success", True) and resp2.status_code not in (200,):
                    return False, f"Account check failed ({resp2.status_code}): {body.get('errors')}"

        return True, f"Token valid (status={status})"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def ensure_auth(non_interactive: bool = False) -> tuple[bool, str]:
    """Ensure credentials are available; optionally run interactive wrangler login."""
    pattern = detect_auth_pattern()
    if pattern in ("api_token", "token_file"):
        ok, msg = verify_credentials()
        return ok, msg

    if non_interactive:
        return False, (
            "NON_INTERACTIVE requires CLOUDFLARE_API_TOKEN "
            "(and CLOUDFLARE_ACCOUNT_ID for deploy)."
        )

    if pattern == "wrangler":
        if setup_wrangler_interactive():
            return True, "Wrangler login completed"
        return False, "Wrangler login failed"

    return False, "No Cloudflare credentials found"
