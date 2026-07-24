"""Tests for OCI Always Free tier constants and validation."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from cloudbooter.free_tier import (
    LIMITS,
    OCIFreeTierLimits,
    ArmInstanceSnapshot,
    TenancySnapshot,
    arm_instance_needs_resize,
    audit_tenancy,
    list_arm_resize_targets,
    resolve_enforce_limits,
    should_auto_resize_legacy_arm,
    validate_proposed_config,
)

OCI_ROOT = Path(__file__).resolve().parents[1]


class TestOCIFreeTierLimitsConstants:
    def test_arm_pool_is_2_ocpu_12gb(self):
        assert LIMITS.max_arm_ocpus == 2
        assert LIMITS.max_arm_memory_gb == 12

    def test_default_billing_safe_profile(self):
        assert LIMITS.default_arm_ocpus == 2
        assert LIMITS.default_arm_memory_gb == 12
        assert LIMITS.default_boot_volume_gb == 200
        assert LIMITS.boot_volume_vpu == 120

    def test_amd_and_storage_limits(self):
        assert LIMITS.max_amd_instances == 2
        assert LIMITS.max_storage_gb == 200
        assert LIMITS.max_arm_instances == 2

    def test_frozen_dataclass(self):
        with pytest.raises((AttributeError, TypeError)):
            LIMITS.max_arm_ocpus = 4  # type: ignore[misc]


class TestValidateProposedConfig:
    def test_billing_safe_valid(self):
        assert validate_proposed_config(0, 1, 2, 12, 200, billing_safe=True) == []

    def test_billing_safe_rejects_amd(self):
        errors = validate_proposed_config(1, 1, 2, 12, 200, billing_safe=True)
        assert any("0 AMD" in e for e in errors)

    def test_rejects_excess_ocpus(self):
        errors = validate_proposed_config(0, 1, 3, 12, 200)
        assert any("ARM OCPUs" in e for e in errors)

    def test_rejects_excess_storage(self):
        errors = validate_proposed_config(0, 1, 2, 12, 201)
        assert any("storage" in e.lower() for e in errors)

    def test_billing_safe_rejects_block_volumes(self):
        errors = validate_proposed_config(
            0, 1, 2, 12, 200, billing_safe=True, block_storage_gb=10
        )
        assert any("block volumes" in e.lower() for e in errors)


class TestResolveEnforceLimits:
    def test_auto_payg(self):
        assert resolve_enforce_limits("PAYG", "auto") is True

    def test_auto_free_tier(self):
        assert resolve_enforce_limits("FREE_TIER", "auto") is False

    def test_false_override(self):
        assert resolve_enforce_limits("PAYG", "false") is False
        assert resolve_enforce_limits("FREE_TIER", "false") is False

    def test_true_override(self):
        assert resolve_enforce_limits("FREE_TIER", "true") is True


class TestAuditTenancy:
    def _snapshot(self, **kwargs) -> TenancySnapshot:
        defaults = {
            "amd_instances": 0,
            "arm_instances": [
                ArmInstanceSnapshot(name="arm-1", ocpus=2, memory_gb=12),
            ],
            "boot_storage_gb": 200,
            "block_storage_gb": 0,
            "block_volume_count": 0,
            "vcn_count": 1,
        }
        defaults.update(kwargs)
        return TenancySnapshot(**defaults)

    def test_happy_path_no_findings(self):
        assert audit_tenancy(self._snapshot()) == []

    def test_extra_arm_instance(self):
        findings = audit_tenancy(
            self._snapshot(
                arm_instances=[
                    ArmInstanceSnapshot(name="a", ocpus=2, memory_gb=12),
                    ArmInstanceSnapshot(name="b", ocpus=2, memory_gb=12),
                ]
            )
        )
        codes = [f.code for f in findings]
        assert "EXTRA_ARM_INSTANCE" in codes

    def test_legacy_arm_sizing(self):
        findings = audit_tenancy(
            self._snapshot(
                arm_instances=[
                    ArmInstanceSnapshot(name="legacy", ocpus=4, memory_gb=24),
                ]
            )
        )
        assert any(f.code == "LEGACY_ARM_SIZING" for f in findings)
        assert any("Resize" in f.remediation for f in findings)

    def test_storage_over_cap(self):
        findings = audit_tenancy(
            self._snapshot(boot_storage_gb=200, block_storage_gb=50)
        )
        assert any(f.code == "STORAGE_OVER_CAP" for f in findings)

    def test_extra_amd(self):
        findings = audit_tenancy(self._snapshot(amd_instances=1))
        assert any(f.code == "EXTRA_AMD" for f in findings)


class TestTenancySnapshotFromDict:
    def test_from_dict_parses_arm_instances(self):
        snap = TenancySnapshot.from_dict(
            {
                "amd_instances": 0,
                "arm_instances": [{"name": "x", "ocpus": 2, "memory_gb": 12}],
                "boot_storage_gb": 200,
            }
        )
        assert snap.amd_instances == 0
        assert len(snap.arm_instances) == 1
        assert snap.arm_instances[0].name == "x"


class TestArmResize:
    def test_needs_resize_legacy_4_24(self):
        arm = ArmInstanceSnapshot(ocpus=4, memory_gb=24)
        assert arm_instance_needs_resize(arm) is True

    def test_no_resize_at_cap(self):
        arm = ArmInstanceSnapshot(ocpus=2, memory_gb=12)
        assert arm_instance_needs_resize(arm) is False

    def test_list_resize_targets(self):
        snap = TenancySnapshot(
            arm_instances=[
                ArmInstanceSnapshot(id="ocid1", name="legacy", ocpus=4, memory_gb=24),
                ArmInstanceSnapshot(id="ocid2", name="ok", ocpus=2, memory_gb=12),
            ]
        )
        targets = list_arm_resize_targets(snap)
        assert len(targets) == 1
        assert targets[0]["id"] == "ocid1"
        assert targets[0]["target_ocpus"] == 2
        assert targets[0]["target_memory_gb"] == 12


class TestShouldAutoResizeLegacyArm:
    def test_resize_only(self):
        assert should_auto_resize_legacy_arm("false", resize_only=True) is True

    def test_auto_non_interactive(self):
        assert should_auto_resize_legacy_arm("auto", non_interactive=True) is True
        assert should_auto_resize_legacy_arm("auto", non_interactive=False) is False

    def test_explicit_true(self):
        assert should_auto_resize_legacy_arm("true", non_interactive=False) is True


class TestScriptConstantSync:
    """Bash and PowerShell FREE_TIER_* must match Python LIMITS."""

    @pytest.fixture
    def bash_constants(self) -> dict[str, int | str]:
        text = (OCI_ROOT / "setup_oci_terraform.sh").read_text()
        return {
            "max_arm_ocpus": int(re.search(r"FREE_TIER_MAX_ARM_OCPUS=(\d+)", text).group(1)),
            "max_arm_memory_gb": int(re.search(r"FREE_TIER_MAX_ARM_MEMORY_GB=(\d+)", text).group(1)),
            "max_storage_gb": int(re.search(r"FREE_TIER_MAX_STORAGE_GB=(\d+)", text).group(1)),
            "default_arm_ocpus": int(re.search(r"FREE_TIER_DEFAULT_ARM_OCPUS=(\d+)", text).group(1)),
            "default_boot_volume_gb": int(
                re.search(r"FREE_TIER_DEFAULT_BOOT_VOLUME_GB=(\d+)", text).group(1)
            ),
            "boot_volume_vpu": int(re.search(r"FREE_TIER_BOOT_VOLUME_VPU=(\d+)", text).group(1)),
        }

    @pytest.fixture
    def ps_constants(self) -> dict[str, int]:
        text = (OCI_ROOT / "setup_oci_terraform.ps1").read_text()
        return {
            "max_arm_ocpus": int(re.search(r"\$FREE_TIER_MAX_ARM_OCPUS = (\d+)", text).group(1)),
            "max_arm_memory_gb": int(
                re.search(r"\$FREE_TIER_MAX_ARM_MEMORY_GB = (\d+)", text).group(1)
            ),
            "max_storage_gb": int(re.search(r"\$FREE_TIER_MAX_STORAGE_GB = (\d+)", text).group(1)),
        }

    def test_bash_matches_python(self, bash_constants: dict[str, int | str]):
        assert bash_constants["max_arm_ocpus"] == LIMITS.max_arm_ocpus
        assert bash_constants["max_arm_memory_gb"] == LIMITS.max_arm_memory_gb
        assert bash_constants["max_storage_gb"] == LIMITS.max_storage_gb
        assert bash_constants["default_arm_ocpus"] == LIMITS.default_arm_ocpus
        assert bash_constants["default_boot_volume_gb"] == LIMITS.default_boot_volume_gb
        assert bash_constants["boot_volume_vpu"] == LIMITS.boot_volume_vpu

    def test_powershell_matches_python(self, ps_constants: dict[str, int]):
        assert ps_constants["max_arm_ocpus"] == LIMITS.max_arm_ocpus
        assert ps_constants["max_arm_memory_gb"] == LIMITS.max_arm_memory_gb
        assert ps_constants["max_storage_gb"] == LIMITS.max_storage_gb
