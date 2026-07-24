"""Tests for multi-account migration orchestration."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from cloudbooter.bitwarden import OciBitwardenAccount
from cloudbooter.multi_account import (
    MigrationReport,
    process_account,
    render_markdown_report,
    run_migration,
    write_report_files,
)


def _ready(slug: str, username: str) -> OciBitwardenAccount:
    return OciBitwardenAccount(
        item_id=f"id-{slug}",
        name=f"Oracle {slug}",
        username=username,
        slug=slug,
        auth_mode="api_key",
        tenancy_ocid=f"ocid1.tenancy.oc1..{slug}",
        user_ocid=f"ocid1.user.oc1..{slug}",
        fingerprint="aa:bb:cc:dd",
        region="us-phoenix-1",
        private_key_pem="-----BEGIN RSA PRIVATE KEY-----\nKEY\n-----END RSA PRIVATE KEY-----",
    )


def _console_only(slug: str) -> OciBitwardenAccount:
    return OciBitwardenAccount(
        item_id=f"id-{slug}",
        name=f"Oracle {slug}",
        username=f"{slug}@example.com",
        slug=slug,
        auth_mode="console_only",
        missing_fields=("tenancy", "user", "fingerprint", "region", "private_key"),
    )


class TestRunMigration:
    def test_dry_run_lists_accounts(self, tmp_path: Path):
        accounts = [_ready("armandfcrouch", "armandfcrouch@example.com"), _console_only("other")]

        def discover(**_kwargs):
            return accounts

        report = run_migration(
            start_account="armandfcrouch",
            dry_run=True,
            state_root=tmp_path,
            discover=discover,
        )
        assert len(report.processed) == 2
        assert report.processed[0].status == "dry_run"
        assert len(report.remaining) == 0

    def test_skipped_console_only_in_remaining(self, tmp_path: Path):
        accounts = [_console_only("other")]

        def discover(**_kwargs):
            return accounts

        report = run_migration(
            account_filter=["other"],
            dry_run=False,
            state_root=tmp_path,
            discover=discover,
        )
        assert report.processed[0].status == "skipped"
        assert report.remaining[0]["status"] == "skipped"

    def test_process_account_uses_setup_script(self, tmp_path: Path):
        account = _ready("armandfcrouch", "armandfcrouch@example.com")
        report_payload = {
            "plan_type": "PAYG",
            "enforce_limits": True,
            "inventory": {
                "amd_instances": 0,
                "arm_instances": [
                    {
                        "id": "ocid1.instance",
                        "name": "legacy",
                        "ocpus": 4,
                        "memory_gb": 24,
                        "shape": "VM.Standard.A1.Flex",
                    }
                ],
                "boot_storage_gb": 200,
                "block_storage_gb": 0,
                "block_volume_count": 0,
                "vcn_count": 1,
                "non_free_shapes": [],
            },
            "resize_outcomes": [
                {
                    "id": "ocid1.instance",
                    "name": "legacy",
                    "before_ocpus": 4,
                    "before_memory_gb": 24,
                    "after_ocpus": 2,
                    "after_memory_gb": 12,
                    "success": True,
                }
            ],
        }

        class FakeProc:
            returncode = 0
            stdout = "ok"
            stderr = ""

        def fake_runner(*_args, **_kwargs):
            report_path = tmp_path / "armandfcrouch" / "report.json"
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps(report_payload), encoding="utf-8")
            return FakeProc()

        result = process_account(
            account,
            state_root=tmp_path,
            runner=fake_runner,
        )
        assert result.status == "processed"
        assert result.plan_type == "PAYG"
        assert len(result.resize_targets) == 1
        assert result.resize_outcomes[0]["success"] is True


class TestReportFiles:
    def test_write_report_files(self, tmp_path: Path):
        report = MigrationReport(
            generated_at="2026-07-24T00:00:00+00:00",
            start_account="armandfcrouch",
            dry_run=True,
            remaining=[
                {
                    "slug": "other",
                    "name": "Oracle other",
                    "username": "other@example.com",
                    "auth_mode": "console_only",
                    "missing_fields": ["tenancy"],
                    "status": "pending",
                }
            ],
        )
        json_path, md_path = write_report_files(report, report_dir=tmp_path)
        assert json_path.is_file()
        assert md_path.is_file()
        md = md_path.read_text(encoding="utf-8")
        assert "armandfcrouch" in render_markdown_report(report)
        assert "Remaining accounts" in md
