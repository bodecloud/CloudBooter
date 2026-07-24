"""Shared pytest fixtures and mock data for cloudbooter-cloudflare tests."""
from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture()
def tmp_tf_dir(tmp_path: Path) -> Path:
    """Fresh empty directory for writing generated Terraform files."""
    return tmp_path


_CF_ENV_KEYS = [
    "CLOUDFLARE_API_TOKEN",
    "CLOUDFLARE_API_TOKEN_FILE",
    "CLOUDFLARE_ACCOUNT_ID",
    "CLOUDFLARE_ZONE_ID",
    "CLOUDFLARE_ZONE_NAME",
    "CLOUDFLARE_WORKER_NAME",
    "CLOUDFLARE_ALLOW_PAID_RESOURCES",
    "CF_MODE",
    "NON_INTERACTIVE",
    "AUTO_DEPLOY",
    "AUTO_USE_EXISTING",
    "SKIP_CONFIG",
]


@pytest.fixture()
def clean_cf_env(monkeypatch: pytest.MonkeyPatch):
    """Remove every Cloudflare-related env var so tests start clean."""
    for key in _CF_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


MOCK_WORKERS: list[dict] = [
    {
        "id": "existing-worker",
        "modified_on": "2026-07-01T00:00:00Z",
        "created_on": "2026-01-01T00:00:00Z",
    }
]

MOCK_KV: list[dict] = [
    {"id": "kv-ns-1", "title": "existing-kv"},
]

MOCK_R2: dict = {
    "buckets": [
        {"name": "existing-bucket", "creation_date": "2026-01-01T00:00:00Z"},
    ]
}

MOCK_D1: list[dict] = [
    {"name": "existing-db", "uuid": "d1-uuid-1"},
]

MOCK_ZONES: list[dict] = [
    {
        "id": "zone-1",
        "name": "example.com",
        "status": "active",
        "account": {"id": "acct-test"},
    }
]
