"""Bitwarden CLI integration for OCI account discovery."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Any, Callable, Literal

AuthMode = Literal["api_key", "console_only", "incomplete"]

_OCI_URI_HINTS = ("cloud.oracle.com", "oraclecloud.com")
_OCI_NAME_HINTS = ("oracle", "oci")

_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "tenancy": ("tenancy", "tenancy_ocid", "tenancy ocid", "tenancy-id"),
    "user": ("user", "user_ocid", "user ocid", "user-id"),
    "fingerprint": ("fingerprint", "api_fingerprint", "key_fingerprint"),
    "region": ("region", "home_region", "home region"),
    "private_key": ("private_key", "api_private_key", "private key", "pem", "key"),
}

_PEM_BEGIN = "-----BEGIN"


@dataclass(frozen=True)
class OciBitwardenAccount:
    """Discovered Bitwarden vault entry for an OCI tenancy."""

    item_id: str
    name: str
    username: str
    slug: str
    auth_mode: AuthMode
    missing_fields: tuple[str, ...] = ()
    tenancy_ocid: str | None = None
    user_ocid: str | None = None
    fingerprint: str | None = None
    region: str | None = None
    private_key_pem: str | None = None
    uris: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "name": self.name,
            "username": self.username,
            "slug": self.slug,
            "auth_mode": self.auth_mode,
            "missing_fields": list(self.missing_fields),
            "tenancy_ocid": self.tenancy_ocid,
            "user_ocid": self.user_ocid,
            "fingerprint": self.fingerprint,
            "region": self.region,
            "uris": list(self.uris),
            "has_private_key": self.private_key_pem is not None,
        }


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "unknown"


def account_slug(name: str, username: str) -> str:
    """Derive a filesystem-safe account slug from BW metadata."""
    for candidate in (username, name):
        if not candidate:
            continue
        local = candidate.split("@", 1)[0]
        if local:
            return _slugify(local)
    return _slugify(name or username or "unknown")


def _normalize_key(key: str) -> str:
    return re.sub(r"[\s_-]+", "_", key.strip().lower())


def _field_map_from_custom_fields(custom_fields: list[dict[str, Any]]) -> dict[str, str]:
    mapped: dict[str, str] = {}
    for cf in custom_fields or []:
        raw_name = str(cf.get("name", ""))
        value = str(cf.get("value", "")).strip()
        if not raw_name or not value:
            continue
        norm = _normalize_key(raw_name)
        for canonical, aliases in _FIELD_ALIASES.items():
            if norm in {_normalize_key(a) for a in aliases}:
                mapped.setdefault(canonical, value)
    return mapped


def _extract_pem_from_text(text: str) -> str | None:
    if not text or _PEM_BEGIN not in text:
        return None
    match = re.search(
        r"(-----BEGIN [A-Z ]+-----.*?-----END [A-Z ]+-----)",
        text,
        re.DOTALL,
    )
    return match.group(1).strip() if match else None


def _item_uris(item: dict[str, Any]) -> list[str]:
    uris: list[str] = []
    login = item.get("login") or {}
    for uri in login.get("uris") or []:
        if uri:
            uris.append(str(uri))
    return uris


def _matches_oci_item(item: dict[str, Any]) -> bool:
    name = str(item.get("name", "")).lower()
    username = str((item.get("login") or {}).get("username", "")).lower()
    uris = [u.lower() for u in _item_uris(item)]

    if any(h in u for u in uris for h in _OCI_URI_HINTS):
        return True
    if any(h in name for h in _OCI_NAME_HINTS):
        return True
    if any(h in username for h in _OCI_NAME_HINTS):
        return True
    return False


def _classify_account(
    item_id: str,
    name: str,
    username: str,
    uris: tuple[str, ...],
    fields: dict[str, str],
    private_key_pem: str | None,
) -> OciBitwardenAccount:
    slug = account_slug(name, username)
    tenancy = fields.get("tenancy")
    user = fields.get("user")
    fingerprint = fields.get("fingerprint")
    region = fields.get("region")

    required_api = {
        "tenancy": tenancy,
        "user": user,
        "fingerprint": fingerprint,
        "region": region,
        "private_key": private_key_pem,
    }
    missing = tuple(k for k, v in required_api.items() if not v)

    if not missing:
        auth_mode: AuthMode = "api_key"
    elif username and not any((tenancy, user, fingerprint, private_key_pem)):
        auth_mode = "console_only"
    else:
        auth_mode = "incomplete"

    return OciBitwardenAccount(
        item_id=item_id,
        name=name,
        username=username,
        slug=slug,
        auth_mode=auth_mode,
        missing_fields=missing,
        tenancy_ocid=tenancy,
        user_ocid=user,
        fingerprint=fingerprint,
        region=region,
        private_key_pem=private_key_pem,
        uris=uris,
    )


def parse_bw_item(item: dict[str, Any]) -> OciBitwardenAccount | None:
    """Parse a Bitwarden item JSON object into an OCI account descriptor."""
    if not _matches_oci_item(item):
        return None

    item_id = str(item.get("id", ""))
    name = str(item.get("name", ""))
    login = item.get("login") or {}
    username = str(login.get("username", ""))
    uris = tuple(_item_uris(item))

    fields = _field_map_from_custom_fields(list(item.get("fields") or []))

    notes = str(item.get("notes") or "")
    private_key = fields.get("private_key") or _extract_pem_from_text(notes)

    return _classify_account(item_id, name, username, uris, fields, private_key)


def dedupe_accounts(accounts: list[OciBitwardenAccount]) -> list[OciBitwardenAccount]:
    """De-dupe by username or tenancy OCID, keeping the best api_key-ready entry."""
    seen: dict[str, OciBitwardenAccount] = {}
    order: list[str] = []

    def keys(acct: OciBitwardenAccount) -> list[str]:
        keys_out: list[str] = []
        if acct.username:
            keys_out.append(f"user:{acct.username.lower()}")
        if acct.tenancy_ocid:
            keys_out.append(f"tenancy:{acct.tenancy_ocid}")
        keys_out.append(f"id:{acct.item_id}")
        return keys_out

    for acct in accounts:
        matched_key: str | None = None
        for key in keys(acct):
            if key in seen:
                matched_key = key
                break

        if matched_key is None:
            primary = keys(acct)[0]
            seen[primary] = acct
            order.append(primary)
            continue

        existing = seen[matched_key]
        if existing.auth_mode != "api_key" and acct.auth_mode == "api_key":
            seen[matched_key] = acct

    return [seen[k] for k in order]


def sort_accounts(
    accounts: list[OciBitwardenAccount],
    start_account: str | None = None,
) -> list[OciBitwardenAccount]:
    """Place start_account first; remaining sorted alphabetically by name."""
    if not start_account:
        return sorted(accounts, key=lambda a: a.name.lower())

    needle = start_account.lower()

    def matches_start(acct: OciBitwardenAccount) -> bool:
        return needle in (
            acct.slug.lower(),
            acct.name.lower(),
            acct.username.lower(),
            acct.username.split("@", 1)[0].lower(),
        )

    starters = [a for a in accounts if matches_start(a)]
    others = sorted(
        [a for a in accounts if not matches_start(a)],
        key=lambda a: a.name.lower(),
    )
    return starters + others


def find_start_account_matches(
    accounts: list[OciBitwardenAccount],
    start_account: str,
) -> list[OciBitwardenAccount]:
    needle = start_account.lower()
    return [
        a
        for a in accounts
        if needle in (
            a.slug.lower(),
            a.name.lower(),
            a.username.lower(),
            a.username.split("@", 1)[0].lower(),
        )
    ]


def require_bw_cli() -> str:
    """Return path to bw binary or raise FileNotFoundError with install hint."""
    path = shutil.which("bw")
    if not path:
        raise FileNotFoundError(
            "Bitwarden CLI (bw) not found on PATH. Install: npm i -g @bitwarden/cli"
        )
    return path


def bw_status(session: str | None = None) -> dict[str, Any]:
    """Return parsed `bw status` JSON."""
    bw = require_bw_cli()
    env = os.environ.copy()
    effective = _resolve_session(session)
    if effective:
        env["BW_SESSION"] = effective
    result = subprocess.run(
        [bw, "status"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "bw status failed")
    return json.loads(result.stdout)


def _run_bw(args: list[str], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    bw = require_bw_cli()
    run_env = os.environ.copy()
    if env:
        run_env.update(env)
    return subprocess.run(
        [bw, *args],
        capture_output=True,
        text=True,
        check=False,
        env=run_env,
    )


def _resolve_session(session: str | None = None) -> str:
    """Resolve BW_SESSION from arg, env, or BW_SESSION_FILE."""
    if session:
        return session
    effective = os.environ.get("BW_SESSION", "")
    if effective:
        return effective
    session_file = os.environ.get("BW_SESSION_FILE", "")
    if session_file:
        path = Path(session_file).expanduser()
        if path.is_file():
            content = path.read_text(encoding="utf-8").strip()
            if content:
                return content
    return ""


def prepare_bitwarden_session(session: str | None = None) -> str:
    """Login/unlock Bitwarden when possible; return BW_SESSION for vault access."""
    effective = _resolve_session(session)
    status = bw_status(effective or None)
    state = status.get("status")

    if state == "unlocked":
        return effective

    if state == "unauthenticated":
        client_id = os.environ.get("BW_CLIENTID", "")
        client_secret = os.environ.get("BW_CLIENTSECRET", "")
        if client_id and client_secret:
            login = _run_bw(["login", "--apikey"])
            if login.returncode != 0:
                raise RuntimeError(
                    login.stderr.strip() or "Bitwarden API-key login failed"
                )
            status = bw_status(None)
            state = status.get("status")
        else:
            raise RuntimeError(
                "Bitwarden is not logged in. Run: bw login "
                "(or set BW_CLIENTID + BW_CLIENTSECRET for API-key login)"
            )

    if state == "locked":
        if effective:
            retry = bw_status(effective)
            if retry.get("status") == "unlocked":
                return effective

        password_env = os.environ.get("BW_PASSWORD_ENV", "BW_PASSWORD")
        if os.environ.get(password_env):
            unlock = _run_bw(["unlock", "--passwordenv", password_env, "--raw"])
            if unlock.returncode != 0:
                raise RuntimeError(unlock.stderr.strip() or "Bitwarden unlock failed")
            effective = unlock.stdout.strip()
            os.environ["BW_SESSION"] = effective
            return effective

        raise RuntimeError(
            "Bitwarden vault is locked. Export BW_SESSION=$(bw unlock --raw) "
            f"or set {password_env} for non-interactive unlock"
        )

    raise RuntimeError(f"Unexpected Bitwarden status: {state}")


def ensure_vault_unlocked(session: str | None = None) -> str:
    """Verify vault is unlocked; return effective BW_SESSION."""
    return prepare_bitwarden_session(session)


def list_bw_items(
    *,
    session: str | None = None,
    runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
) -> list[dict[str, Any]]:
    """Fetch all vault items via `bw list items`."""
    env = os.environ.copy()
    effective = _resolve_session(session)
    if effective:
        env["BW_SESSION"] = effective

    run = runner or subprocess.run
    if runner is None:
        bw = require_bw_cli()
        cmd = [bw, "list", "items"]
    else:
        cmd = ["bw", "list", "items"]

    result = run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "bw list items failed")
    data = json.loads(result.stdout)
    if not isinstance(data, list):
        raise RuntimeError("Unexpected bw list items output")
    return data


def load_items_file(path: Path | str) -> list[dict[str, Any]]:
    """Load decrypted Bitwarden items from a `bw list items` JSON export."""
    file_path = Path(path).expanduser()
    if not file_path.is_file():
        raise FileNotFoundError(f"Bitwarden items file not found: {file_path}")
    data = json.loads(file_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise RuntimeError(f"Expected JSON array in {file_path}")
    return data


def discover_oci_accounts_from_items(
    items: list[dict[str, Any]],
    *,
    start_account: str | None = None,
) -> list[OciBitwardenAccount]:
    """Classify OCI accounts from pre-exported Bitwarden item JSON."""
    accounts: list[OciBitwardenAccount] = []
    for item in items:
        parsed = parse_bw_item(item)
        if parsed is not None:
            accounts.append(parsed)
    accounts = dedupe_accounts(accounts)
    return sort_accounts(accounts, start_account=start_account)


def default_items_file() -> Path:
    """Default offline export path (BW_ITEMS_FILE or cloud/OCI/.bw-items.json)."""
    override = os.environ.get("BW_ITEMS_FILE", "")
    if override:
        return Path(override).expanduser()
    return Path(__file__).resolve().parents[2] / ".bw-items.json"


def discover_oci_accounts(
    *,
    session: str | None = None,
    start_account: str | None = None,
    runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
    skip_unlock_check: bool = False,
) -> list[OciBitwardenAccount]:
    """Discover and classify OCI-related Bitwarden vault entries."""
    if not skip_unlock_check and runner is None:
        ensure_vault_unlocked(session)
    items = list_bw_items(session=session, runner=runner)
    accounts: list[OciBitwardenAccount] = []
    for item in items:
        parsed = parse_bw_item(item)
        if parsed is not None:
            accounts.append(parsed)
    accounts = dedupe_accounts(accounts)
    return sort_accounts(accounts, start_account=start_account)
