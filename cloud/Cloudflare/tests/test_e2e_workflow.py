"""End-to-end workflow tests via Click CliRunner."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from cloudbooter.cli import main


def _run(*args, extra_env: dict | None = None):
    runner = CliRunner()
    env = {k: v for k, v in os.environ.items()}
    if extra_env:
        env.update(extra_env)
    return runner.invoke(main, list(args), catch_exceptions=False, env=env)


class TestCLISanity:
    def test_version_flag(self):
        result = _run("--version")
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_help_lists_commands(self):
        result = _run("--help")
        assert result.exit_code == 0
        for cmd in ("deploy", "validate", "inventory", "install-deps"):
            assert cmd in result.output


class TestValidateCommand:
    def test_valid_config_exits_0(self):
        result = _run("validate")
        assert result.exit_code == 0
        assert "✓" in result.output or "within" in result.output.lower()

    def test_bad_cpu_exits_1(self):
        result = _run("validate", "--workers-cpu-ms", "50")
        assert result.exit_code == 1
        assert "ERROR:" in result.output

    def test_bad_r2_class_exits_1(self):
        result = _run("validate", "--r2-storage-class", "InfrequentAccess")
        assert result.exit_code == 1

    def test_allow_paid_overrides(self):
        result = _run("validate", "--workers-cpu-ms", "50", "--allow-paid")
        assert result.exit_code == 0

    def test_load_balancer_blocked(self):
        result = _run("validate", "--enable-load-balancer")
        assert result.exit_code == 1


class TestDeployCommand:
    def test_writes_core_files(self, tmp_path: Path):
        result = _run(
            "deploy",
            "--account-id", "acct-test",
            "--api-token", "cf-token",
            "--output-dir", str(tmp_path),
            "--no-auto-deploy",
            "--non-interactive",
        )
        assert result.exit_code == 0
        for fname in ("provider.tf", "variables.tf", "main.tf", "worker.mjs"):
            assert (tmp_path / fname).exists(), f"Missing: {fname}"
            assert (tmp_path / fname).stat().st_size > 0

    def test_bad_cpu_blocks_generation(self, tmp_path: Path):
        result = _run(
            "deploy",
            "--account-id", "acct",
            "--api-token", "tok",
            "--workers-cpu-ms", "50",
            "--output-dir", str(tmp_path),
            "--no-auto-deploy",
            "--non-interactive",
        )
        assert result.exit_code == 1
        assert list(tmp_path.glob("*.tf")) == []

    def test_non_interactive_requires_token(self, tmp_path: Path):
        result = _run(
            "deploy",
            "--account-id", "acct",
            "--output-dir", str(tmp_path),
            "--no-auto-deploy",
            "--non-interactive",
            extra_env={"CLOUDFLARE_API_TOKEN": ""},
        )
        # Click may still pass empty string; our check should fail
        assert result.exit_code == 1

    def test_env_vars_for_account(self, tmp_path: Path):
        result = _run(
            "deploy",
            "--output-dir", str(tmp_path),
            "--no-auto-deploy",
            "--non-interactive",
            extra_env={
                "CLOUDFLARE_ACCOUNT_ID": "env-acct",
                "CLOUDFLARE_API_TOKEN": "env-tok",
                "CLOUDFLARE_WORKER_NAME": "env-worker",
            },
        )
        assert result.exit_code == 0
        vars_content = (tmp_path / "variables.tf").read_text(encoding="utf-8")
        assert "env-acct" in vars_content
        assert "env-worker" in vars_content

    def test_provider_uses_cloudflare(self, tmp_path: Path):
        result = _run(
            "deploy",
            "--account-id", "a",
            "--api-token", "t",
            "--output-dir", str(tmp_path),
            "--no-auto-deploy",
            "--non-interactive",
        )
        assert result.exit_code == 0
        provider = (tmp_path / "provider.tf").read_text(encoding="utf-8")
        assert 'provider "cloudflare"' in provider
        assert 'version = "~> 5"' in provider


class TestInventoryCommand:
    def test_inventory_calls_helpers(self):
        from cloudbooter.inventory import ResourceInventory

        inv = ResourceInventory()
        with patch("cloudbooter.inventory.run_full_inventory", return_value=inv) as mock_inv:
            with patch("cloudbooter.inventory.display_inventory_dashboard") as mock_dash:
                result = _run("inventory", "--account-id", "acct")
        assert result.exit_code == 0
        mock_inv.assert_called_once()
        mock_dash.assert_called_once()


class TestInstallDepsCommand:
    def test_runs(self):
        with patch("cloudbooter.installer.install_wrangler", return_value="api"):
            with patch("cloudbooter.installer.install_terraform", return_value=True):
                with patch("cloudbooter.installer.ensure_python_deps"):
                    result = _run("install-deps")
        assert result.exit_code == 0
        assert "CF_MODE=" in result.output


class TestFullPipelineE2E:
    def test_end_to_end_valid_config(self, tmp_path: Path):
        v = _run("validate")
        assert v.exit_code == 0

        d = _run(
            "deploy",
            "--account-id", "e2e-acct",
            "--api-token", "e2e-tok",
            "--worker-name", "e2e-worker",
            "--output-dir", str(tmp_path),
            "--no-auto-deploy",
            "--non-interactive",
        )
        assert d.exit_code == 0

        provider = (tmp_path / "provider.tf").read_text(encoding="utf-8")
        variables = (tmp_path / "variables.tf").read_text(encoding="utf-8")
        main_tf = (tmp_path / "main.tf").read_text(encoding="utf-8")
        worker = (tmp_path / "worker.mjs").read_text(encoding="utf-8")

        assert 'provider "cloudflare"' in provider
        assert 'variable "account_id"' in variables
        assert 'resource "cloudflare_workers_script"' in main_tf
        assert "export default" in worker

    def test_idempotency_two_deploys(self, tmp_path: Path):
        common = [
            "deploy",
            "--account-id", "a",
            "--api-token", "t",
            "--output-dir", str(tmp_path),
            "--no-auto-deploy",
            "--non-interactive",
        ]
        _run(*common)
        first = {f.name: f.read_text(encoding="utf-8") for f in tmp_path.glob("*.tf")}
        _run(*common)
        second = {f.name: f.read_text(encoding="utf-8") for f in tmp_path.glob("*.tf")}
        assert first == second

    @pytest.mark.skipif(not shutil.which("terraform"), reason="terraform not on PATH")
    def test_terraform_validate_on_generated_output(self, tmp_path: Path):
        _run(
            "deploy",
            "--account-id", "a",
            "--api-token", "t",
            "--output-dir", str(tmp_path),
            "--no-auto-deploy",
            "--non-interactive",
        )
        r = subprocess.run(
            ["terraform", "init", "-backend=false", "-input=false"],
            cwd=tmp_path,
            capture_output=True,
            check=False,
        )
        assert r.returncode == 0, f"terraform init:\n{r.stderr.decode()}"
        r = subprocess.run(
            ["terraform", "validate"],
            cwd=tmp_path,
            capture_output=True,
            check=False,
        )
        assert r.returncode == 0, f"terraform validate:\n{r.stdout.decode()}\n{r.stderr.decode()}"
