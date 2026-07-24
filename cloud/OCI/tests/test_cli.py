"""Tests for cloudbooter CLI JSON contracts."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

OCI_ROOT = Path(__file__).resolve().parents[1]


def _run_cli(*args: str, stdin: str = "") -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(OCI_ROOT / "src")
    return subprocess.run(
        [sys.executable, "-m", "cloudbooter.cli", *args],
        input=stdin,
        text=True,
        capture_output=True,
        cwd=OCI_ROOT,
        env=env,
    )


class TestCliAudit:
    def test_audit_clean_snapshot_json(self):
        payload = json.dumps(
            {
                "amd_instances": 0,
                "arm_instances": [{"name": "arm-1", "ocpus": 2, "memory_gb": 12}],
                "boot_storage_gb": 200,
                "block_storage_gb": 0,
                "block_volume_count": 0,
                "vcn_count": 1,
            }
        )
        result = _run_cli("audit", "--stdin-json", "--json", stdin=payload)
        assert result.returncode == 0
        assert json.loads(result.stdout) == []

    def test_audit_extra_arm_human_output(self):
        payload = json.dumps(
            {
                "amd_instances": 0,
                "arm_instances": [
                    {"name": "a", "ocpus": 2, "memory_gb": 12},
                    {"name": "b", "ocpus": 2, "memory_gb": 12},
                ],
                "boot_storage_gb": 200,
            }
        )
        result = _run_cli("audit", "--stdin-json", stdin=payload)
        assert result.returncode == 0
        assert "EXTRA_ARM_INSTANCE" not in result.stdout
        assert "2 ARM instances" in result.stdout


class TestCliResolveEnforce:
    def test_resolve_payg_auto(self):
        result = _run_cli(
            "resolve-enforce", "--plan-type", "PAYG", "--env-value", "auto"
        )
        assert result.returncode == 0
        assert result.stdout.strip() == "true"

    def test_resolve_free_tier_auto(self):
        result = _run_cli(
            "resolve-enforce", "--plan-type", "FREE_TIER", "--env-value", "auto"
        )
        assert result.stdout.strip() == "false"


class TestCliValidate:
    def test_validate_billing_safe_ok(self):
        payload = json.dumps(
            {
                "amd_instances": 0,
                "arm_instances": 1,
                "arm_ocpus_total": 2,
                "arm_memory_gb_total": 12,
                "total_storage_gb": 200,
                "billing_safe": True,
                "block_storage_gb": 0,
            }
        )
        result = _run_cli("validate", "--stdin-json", stdin=payload)
        assert result.returncode == 0

    def test_validate_billing_safe_rejects_two_arm(self):
        payload = json.dumps(
            {
                "amd_instances": 0,
                "arm_instances": 2,
                "arm_ocpus_total": 4,
                "arm_memory_gb_total": 24,
                "total_storage_gb": 200,
                "billing_safe": True,
            }
        )
        result = _run_cli("validate", "--stdin-json", stdin=payload)
        assert result.returncode == 1
        assert "exactly 1 ARM" in result.stdout


class TestCliResizeCandidates:
    def test_lists_legacy_instance(self):
        payload = json.dumps(
            {
                "arm_instances": [
                    {"id": "ocid1.arm", "name": "legacy", "ocpus": 4, "memory_gb": 24},
                ]
            }
        )
        result = _run_cli("resize-candidates", "--stdin-json", stdin=payload)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert len(data) == 1
        assert data[0]["target_ocpus"] == 2


class TestCliBwListAccounts:
    def test_bw_list_accounts_json(self, monkeypatch):
        from cloudbooter.bitwarden import parse_bw_item
        import cloudbooter.cli as cli_mod
        from argparse import Namespace

        sample = parse_bw_item(
            {
                "id": "1",
                "name": "Oracle armandfcrouch",
                "login": {
                    "username": "armandfcrouch@example.com",
                    "uris": ["https://cloud.oracle.com"],
                },
                "fields": [
                    {"name": "tenancy_ocid", "value": "ocid1.tenancy.oc1..aaa"},
                    {"name": "user_ocid", "value": "ocid1.user.oc1..bbb"},
                    {"name": "fingerprint", "value": "fp"},
                    {"name": "region", "value": "us-phoenix-1"},
                    {"name": "private_key", "value": "-----BEGIN RSA PRIVATE KEY-----\nK\n-----END RSA PRIVATE KEY-----"},
                ],
            }
        )

        def fake_discover(**_kwargs):
            assert sample is not None
            return [sample]

        monkeypatch.setattr(cli_mod, "discover_oci_accounts", fake_discover)
        args = Namespace(session=None, start_account=None, items_file=None, json=True)
        assert cli_mod.cmd_bw_list_accounts(args) == 0


class TestCliBwResizeAll:
    def test_bw_resize_all_dry_run(self, monkeypatch, capsys):
        from cloudbooter.bitwarden import OciBitwardenAccount
        from cloudbooter.multi_account import AccountRunResult, MigrationReport
        import cloudbooter.cli as cli_mod
        from argparse import Namespace

        acct = OciBitwardenAccount(
            item_id="1",
            name="Oracle",
            username="armandfcrouch@example.com",
            slug="armandfcrouch",
            auth_mode="api_key",
        )
        report = MigrationReport(
            generated_at="2026-07-24T00:00:00+00:00",
            start_account="armandfcrouch",
            dry_run=True,
            processed=[AccountRunResult(account=acct, status="dry_run")],
        )

        monkeypatch.setattr(cli_mod, "run_migration", lambda **_kwargs: report)
        monkeypatch.setattr(
            cli_mod,
            "write_report_files",
            lambda _report, report_dir=None: (Path("a.json"), Path("a.md")),
        )

        args = Namespace(
            start_account="armandfcrouch",
            accounts=None,
            dry_run=True,
            session=None,
            items_file=None,
            report_dir=None,
            json=True,
        )
        assert cli_mod.cmd_bw_resize_all(args) == 0
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["dry_run"] is True
