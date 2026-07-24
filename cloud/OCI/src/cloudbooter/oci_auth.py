"""Materialize OCI CLI config files from Bitwarden credentials."""
from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path

from cloudbooter.bitwarden import OciBitwardenAccount


@dataclass(frozen=True)
class OciCredentialPaths:
    """Paths to generated OCI config artifacts."""

    state_dir: Path
    config_file: Path
    key_file: Path
    profile: str = "DEFAULT"


class OciCredentialError(ValueError):
    """Raised when credential material is incomplete or invalid."""


def validate_api_key_account(account: OciBitwardenAccount) -> None:
    """Ensure account has complete API-key material."""
    if account.auth_mode != "api_key":
        missing = ", ".join(account.missing_fields) or account.auth_mode
        raise OciCredentialError(
            f"Account '{account.name}' is not API-key ready ({missing})"
        )


def materialize_oci_config(
    account: OciBitwardenAccount,
    state_root: Path | str,
    *,
    profile: str = "DEFAULT",
) -> OciCredentialPaths:
    """Write OCI config + PEM key for an account under state_root/<slug>/."""
    validate_api_key_account(account)

    root = Path(state_root)
    state_dir = root / account.slug
    state_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(state_dir, stat.S_IRWXU)

    key_file = state_dir / "oci_api_key.pem"
    config_file = state_dir / "config"

    assert account.private_key_pem is not None
    key_file.write_text(account.private_key_pem.strip() + "\n", encoding="utf-8")
    os.chmod(key_file, stat.S_IRUSR | stat.S_IWUSR)

    config_body = (
        f"[{profile}]\n"
        f"tenancy={account.tenancy_ocid}\n"
        f"user={account.user_ocid}\n"
        f"fingerprint={account.fingerprint}\n"
        f"key_file={key_file}\n"
        f"region={account.region}\n"
    )
    config_file.write_text(config_body, encoding="utf-8")
    os.chmod(config_file, stat.S_IRUSR | stat.S_IWUSR)

    return OciCredentialPaths(
        state_dir=state_dir,
        config_file=config_file,
        key_file=key_file,
        profile=profile,
    )


def cleanup_credential_paths(paths: OciCredentialPaths) -> None:
    """Remove generated config artifacts."""
    for path in (paths.config_file, paths.key_file):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
    try:
        paths.state_dir.rmdir()
    except OSError:
        pass
