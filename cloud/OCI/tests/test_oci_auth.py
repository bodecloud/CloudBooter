"""Tests for OCI config materialization from Bitwarden credentials."""
from __future__ import annotations

import stat
from pathlib import Path

import pytest

from cloudbooter.bitwarden import OciBitwardenAccount
from cloudbooter.oci_auth import (
    OciCredentialError,
    cleanup_credential_paths,
    materialize_oci_config,
)


def _ready_account() -> OciBitwardenAccount:
    return OciBitwardenAccount(
        item_id="id",
        name="Oracle",
        username="armandfcrouch@example.com",
        slug="armandfcrouch",
        auth_mode="api_key",
        tenancy_ocid="ocid1.tenancy.oc1..aaa",
        user_ocid="ocid1.user.oc1..bbb",
        fingerprint="aa:bb:cc:dd",
        region="us-phoenix-1",
        private_key_pem="-----BEGIN RSA PRIVATE KEY-----\nKEY\n-----END RSA PRIVATE KEY-----",
    )


class TestMaterializeOciConfig:
    def test_writes_config_and_pem(self, tmp_path: Path):
        account = _ready_account()
        paths = materialize_oci_config(account, tmp_path)
        assert paths.config_file.is_file()
        assert paths.key_file.is_file()
        config = paths.config_file.read_text(encoding="utf-8")
        assert "tenancy=ocid1.tenancy.oc1..aaa" in config
        assert str(paths.key_file) in config
        mode = paths.key_file.stat().st_mode
        assert mode & stat.S_IRWXG == 0
        cleanup_credential_paths(paths)
        assert not paths.config_file.exists()

    def test_rejects_incomplete_without_secret_leak(self):
        account = OciBitwardenAccount(
            item_id="id",
            name="Oracle",
            username="user@example.com",
            slug="user",
            auth_mode="incomplete",
            missing_fields=("private_key",),
        )
        with pytest.raises(OciCredentialError) as exc:
            materialize_oci_config(account, "/tmp")
        assert "private_key" not in str(exc.value).lower() or "not api-key ready" in str(
            exc.value
        ).lower()
