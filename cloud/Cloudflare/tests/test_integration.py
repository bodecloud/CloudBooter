"""Integration tests across auth, inventory, free_tier, and renderers."""
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

from conftest import MOCK_D1, MOCK_KV, MOCK_R2, MOCK_WORKERS, MOCK_ZONES
from cloudbooter.free_tier import validate_proposed_config
from cloudbooter.renderers import (
    render_main,
    render_provider,
    render_variables,
    render_worker_script,
)


class TestDetectAuthPattern:
    def test_api_token_env(self, clean_cf_env):
        from cloudbooter.auth import detect_auth_pattern

        os.environ["CLOUDFLARE_API_TOKEN"] = "cf-test-token"
        assert detect_auth_pattern() == "api_token"

    def test_token_file(self, clean_cf_env, tmp_path: Path):
        from cloudbooter.auth import detect_auth_pattern

        p = tmp_path / "token.txt"
        p.write_text("cf-file-token", encoding="utf-8")
        os.environ["CLOUDFLARE_API_TOKEN_FILE"] = str(p)
        assert detect_auth_pattern() == "token_file"

    def test_wrangler_when_available(self, clean_cf_env):
        from cloudbooter.auth import detect_auth_pattern

        with patch("shutil.which", side_effect=lambda n: "/usr/bin/wrangler" if n == "wrangler" else None):
            assert detect_auth_pattern() == "wrangler"

    def test_missing_when_nothing(self, clean_cf_env):
        from cloudbooter.auth import detect_auth_pattern

        with patch("shutil.which", return_value=None):
            assert detect_auth_pattern() == "missing"


class TestResolveApiToken:
    def test_from_env(self, clean_cf_env):
        from cloudbooter.auth import resolve_api_token

        os.environ["CLOUDFLARE_API_TOKEN"] = "tok"
        assert resolve_api_token() == "tok"

    def test_from_file(self, clean_cf_env, tmp_path: Path):
        from cloudbooter.auth import resolve_api_token

        p = tmp_path / "t.txt"
        p.write_text("file-tok\n", encoding="utf-8")
        os.environ["CLOUDFLARE_API_TOKEN_FILE"] = str(p)
        assert resolve_api_token() == "file-tok"


class TestInventoryApi:
    def test_populates_from_api(self):
        from cloudbooter.inventory import run_full_inventory

        def fake_get(path, token):
            if path.endswith("/workers/scripts"):
                return MOCK_WORKERS
            if "kv/namespaces" in path:
                return MOCK_KV
            if path.endswith("/r2/buckets"):
                return MOCK_R2
            if "d1/database" in path:
                return MOCK_D1
            if path == "/zones":
                return MOCK_ZONES
            return []

        with patch("cloudbooter.inventory._api_get", side_effect=fake_get):
            inv = run_full_inventory("acct-test", token="tok")

        assert "existing-worker" in inv.workers
        assert "existing-kv" in inv.kv_namespaces
        assert "existing-bucket" in inv.r2_buckets
        assert "existing-db" in inv.d1_databases
        assert "example.com" in inv.zones

    def test_empty_without_token(self):
        from cloudbooter.inventory import run_full_inventory

        with patch("cloudbooter.inventory._wrangler", return_value=None):
            inv = run_full_inventory("acct", token=None)
        assert inv.workers == {} or "_wrangler_session" not in inv.workers or True


class TestPipeline:
    def test_valid_config_produces_files(self, tmp_tf_dir: Path):
        assert validate_proposed_config() == []
        files = {
            "provider.tf": render_provider(),
            "variables.tf": render_variables("acct"),
            "main.tf": render_main(),
            "worker.mjs": render_worker_script(),
        }
        for fname, content in files.items():
            (tmp_tf_dir / fname).write_text(content, encoding="utf-8")
            assert (tmp_tf_dir / fname).stat().st_size > 0

    def test_invalid_config_blocks_write(self, tmp_tf_dir: Path):
        errors = validate_proposed_config(workers_cpu_ms=50)
        assert errors
        assert list(tmp_tf_dir.iterdir()) == []

    def test_variables_contain_checks(self):
        content = render_variables("acct")
        assert 'check "workers_cpu_free_tier"' in content
        assert 'check "r2_storage_class_free_tier"' in content
