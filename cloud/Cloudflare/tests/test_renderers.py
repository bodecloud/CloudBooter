"""Tests for Terraform HCL renderers (Cloudflare)."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from cloudbooter.renderers import (
    render_d1,
    render_kv,
    render_main,
    render_provider,
    render_r2,
    render_variables,
    render_worker_script,
)


def _bad_indent_lines(text: str) -> list[str]:
    bad = []
    for line in text.splitlines():
        if not line or line[0] != " ":
            continue
        n = len(line) - len(line.lstrip(" "))
        if n % 2 != 0:
            bad.append(repr(line))
    return bad


class TestRenderProvider:
    def test_required_version_constraint(self):
        out = render_provider()
        assert 'required_version = ">= 1.6.0"' in out

    def test_cloudflare_provider_source(self):
        out = render_provider()
        assert 'source  = "cloudflare/cloudflare"' in out

    def test_cloudflare_provider_version_pin(self):
        out = render_provider()
        assert 'version = "~> 5"' in out

    def test_api_token_var_reference(self):
        out = render_provider()
        assert "api_token = var.cloudflare_api_token" in out

    def test_two_space_indent(self):
        bad = _bad_indent_lines(render_provider())
        assert bad == [], f"Non-2-space indent lines: {bad}"

    def test_idempotent(self):
        assert render_provider() == render_provider()


class TestRenderVariables:
    def test_account_id_variable(self):
        out = render_variables("acct-123")
        assert 'variable "account_id"' in out
        assert '"acct-123"' in out

    def test_worker_name_default(self):
        out = render_variables("acct", worker_name="my-worker")
        assert '"my-worker"' in out

    def test_workers_cpu_check_present(self):
        out = render_variables("acct")
        assert 'check "workers_cpu_free_tier"' in out
        assert "<= 10" in out

    def test_r2_storage_class_check_present(self):
        out = render_variables("acct")
        assert 'check "r2_storage_class_free_tier"' in out
        assert 'var.r2_storage_class == "Standard"' in out

    def test_do_backend_check_present(self):
        out = render_variables("acct")
        assert 'check "do_backend_free_tier"' in out
        assert 'var.do_backend == "sqlite"' in out

    def test_load_balancer_check_present(self):
        out = render_variables("acct")
        assert 'check "load_balancer_blocked"' in out

    def test_zone_var_absent_by_default(self):
        out = render_variables("acct")
        assert 'variable "zone_id"' not in out

    def test_zone_var_present_when_requested(self):
        out = render_variables("acct", zone_id="zone-1", include_zone=True)
        assert 'variable "zone_id"' in out
        assert '"zone-1"' in out

    def test_api_token_sensitive(self):
        out = render_variables("acct")
        assert 'variable "cloudflare_api_token"' in out
        assert "sensitive   = true" in out

    def test_two_space_indent(self):
        bad = _bad_indent_lines(render_variables("acct"))
        assert bad == [], f"Non-2-space indent lines: {bad}"

    def test_idempotent(self):
        assert render_variables("acct") == render_variables("acct")


class TestRenderMain:
    def test_workers_script_declared(self):
        out = render_main()
        assert 'resource "cloudflare_workers_script" "app"' in out

    def test_kv_namespace_declared(self):
        out = render_main()
        assert 'resource "cloudflare_workers_kv_namespace" "kv"' in out

    def test_r2_bucket_declared(self):
        out = render_main()
        assert 'resource "cloudflare_r2_bucket" "bucket"' in out

    def test_d1_database_declared(self):
        out = render_main()
        assert 'resource "cloudflare_d1_database" "db"' in out

    def test_workers_dev_subdomain_declared(self):
        out = render_main()
        assert 'resource "cloudflare_workers_script_subdomain" "workers_dev"' in out

    def test_content_file_and_sha256(self):
        out = render_main()
        assert "content_file" in out
        assert "content_sha256" in out
        assert "filesha256" in out

    def test_cpu_ms_from_var(self):
        out = render_main()
        assert "cpu_ms = var.workers_cpu_ms" in out

    def test_kv_binding_present(self):
        out = render_main()
        assert 'type         = "kv_namespace"' in out

    def test_r2_binding_present(self):
        out = render_main()
        assert 'type        = "r2_bucket"' in out

    def test_d1_binding_present(self):
        out = render_main()
        assert 'type        = "d1"' in out

    def test_can_disable_kv(self):
        out = render_main(include_kv=False)
        assert "cloudflare_workers_kv_namespace" not in out

    def test_output_worker_name(self):
        out = render_main()
        assert 'output "worker_name"' in out

    def test_idempotent(self):
        assert render_main() == render_main()


class TestRenderWorkerScript:
    def test_export_default(self):
        out = render_worker_script()
        assert "export default" in out

    def test_fetch_handler(self):
        out = render_worker_script()
        assert "async fetch" in out

    def test_idempotent(self):
        assert render_worker_script() == render_worker_script()


class TestOptionalModules:
    def test_kv_module(self):
        assert 'resource "cloudflare_workers_kv_namespace"' in render_kv()

    def test_r2_module(self):
        assert 'resource "cloudflare_r2_bucket"' in render_r2()

    def test_d1_module(self):
        assert 'resource "cloudflare_d1_database"' in render_d1()


@pytest.mark.skipif(not shutil.which("terraform"), reason="terraform not on PATH")
class TestTerraformValidate:
    def test_generated_files_pass_terraform_validate(self, tmp_tf_dir: Path):
        (tmp_tf_dir / "provider.tf").write_text(render_provider(), encoding="utf-8")
        (tmp_tf_dir / "variables.tf").write_text(render_variables("acct"), encoding="utf-8")
        (tmp_tf_dir / "main.tf").write_text(render_main(), encoding="utf-8")
        (tmp_tf_dir / "worker.mjs").write_text(render_worker_script(), encoding="utf-8")

        r = subprocess.run(
            ["terraform", "init", "-backend=false", "-input=false"],
            cwd=tmp_tf_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        assert r.returncode == 0, f"terraform init failed:\n{r.stderr}"

        r = subprocess.run(
            ["terraform", "validate"],
            cwd=tmp_tf_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        assert r.returncode == 0, f"terraform validate failed:\n{r.stdout}\n{r.stderr}"
