"""OCI Always Free Tier hard limits — canonical source for all layers.

Keep in sync with:
  - shell: setup_oci_terraform.sh constants block
  - powershell: setup_oci_terraform.ps1 $FREE_TIER_* variables
  - Terraform: variables.tf check blocks
  - docs: docs/FREE_TIER_LIMITS.md

Ref: https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm
     https://guides.viren070.me/selfhosting/oracle (billing-safe profile)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

FindingSeverity = Literal["info", "warn", "error"]


@dataclass(frozen=True)
class OCIFreeTierLimits:
    # ── Compute ───────────────────────────────────────────────────────────────
    max_amd_instances: int = 2
    amd_shape: str = "VM.Standard.E2.1.Micro"
    max_arm_ocpus: int = 2
    max_arm_memory_gb: int = 12
    arm_shape: str = "VM.Standard.A1.Flex"
    max_arm_instances: int = 2
    default_arm_ocpus: int = 2
    default_arm_memory_gb: int = 12

    # ── Storage ───────────────────────────────────────────────────────────────
    max_storage_gb: int = 200
    min_boot_volume_gb: int = 47
    default_boot_volume_gb: int = 200
    boot_volume_vpu: int = 120
    max_volume_backups: int = 5

    # ── Networking ──────────────────────────────────────────────────────────────
    max_vcns: int = 2
    outbound_data_transfer_tb: int = 10

    # ── Object storage (Always Free only, post-trial) ─────────────────────────
    max_object_storage_gb: int = 20
    max_object_api_requests_per_month: int = 50_000


LIMITS = OCIFreeTierLimits()


@dataclass(frozen=True)
class ArmInstanceSnapshot:
    id: str = ""
    name: str = ""
    ocpus: int = 0
    memory_gb: int = 0
    shape: str = LIMITS.arm_shape


def arm_instance_needs_resize(arm: ArmInstanceSnapshot) -> bool:
    """True when an A1 Flex instance exceeds current Always Free per-shape caps."""
    if arm.shape and arm.shape != LIMITS.arm_shape:
        return False
    return arm.ocpus > LIMITS.max_arm_ocpus or arm.memory_gb > LIMITS.max_arm_memory_gb


def list_arm_resize_targets(snapshot: TenancySnapshot) -> list[dict[str, str | int]]:
    """ARM instances that should be downsized to the billing-safe 2/12 profile."""
    targets: list[dict[str, str | int]] = []
    for arm in snapshot.arm_instances:
        if not arm_instance_needs_resize(arm):
            continue
        targets.append(
            {
                "id": arm.id,
                "name": arm.name,
                "ocpus": arm.ocpus,
                "memory_gb": arm.memory_gb,
                "target_ocpus": LIMITS.default_arm_ocpus,
                "target_memory_gb": LIMITS.default_arm_memory_gb,
            }
        )
    return targets


def should_auto_resize_legacy_arm(
    env_value: str | None,
    *,
    non_interactive: bool = False,
    resize_only: bool = False,
) -> bool:
    """Whether setup scripts should resize legacy ARM instances without prompting."""
    if resize_only:
        return True
    normalized = (env_value or "auto").strip().lower()
    if normalized in {"true", "yes", "1"}:
        return True
    if normalized in {"false", "no", "0"}:
        return False
    return non_interactive


@dataclass
class TenancySnapshot:
    amd_instances: int = 0
    arm_instances: list[ArmInstanceSnapshot] = field(default_factory=list)
    boot_storage_gb: int = 0
    block_storage_gb: int = 0
    block_volume_count: int = 0
    vcn_count: int = 0
    non_free_shapes: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TenancySnapshot:
        arm_raw = data.get("arm_instances") or []
        arm_instances = [
            ArmInstanceSnapshot(
                id=str(item.get("id", "")),
                name=str(item.get("name", "")),
                ocpus=int(item.get("ocpus", 0)),
                memory_gb=int(item.get("memory_gb", 0)),
                shape=str(item.get("shape", LIMITS.arm_shape)),
            )
            for item in arm_raw
        ]
        return cls(
            amd_instances=int(data.get("amd_instances", 0)),
            arm_instances=arm_instances,
            boot_storage_gb=int(data.get("boot_storage_gb", 0)),
            block_storage_gb=int(data.get("block_storage_gb", 0)),
            block_volume_count=int(data.get("block_volume_count", 0)),
            vcn_count=int(data.get("vcn_count", 0)),
            non_free_shapes=[str(s) for s in (data.get("non_free_shapes") or [])],
        )


@dataclass(frozen=True)
class AuditFinding:
    code: str
    severity: FindingSeverity
    message: str
    remediation: str = ""

    def to_dict(self) -> dict[str, str]:
        result: dict[str, str] = {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
        }
        if self.remediation:
            result["remediation"] = self.remediation
        return result


def resolve_enforce_limits(plan_type: str | None, env_value: str | None) -> bool:
    """Return whether strict limit enforcement should be active.

    env_value: auto | true | false (case-insensitive)
    plan_type: PAYG | FREE_TIER | unknown | None
    """
    normalized_env = (env_value or "auto").strip().lower()
    if normalized_env == "false":
        return False
    if normalized_env == "true":
        return True

    normalized_plan = (plan_type or "unknown").strip().upper()
    return normalized_plan == "PAYG"


def audit_tenancy(snapshot: TenancySnapshot) -> list[AuditFinding]:
    """Compare live tenancy inventory to billing-safe / Always Free expectations.

    Existing drift is reported as warnings — it does not block billing-safe apply.
    """
    findings: list[AuditFinding] = []
    limits = LIMITS
    resize_hint = (
        f"Resize to {limits.default_arm_ocpus} OCPU / "
        f"{limits.default_arm_memory_gb} GB (see docs/FREE_TIER_LIMITS.md)"
    )

    if snapshot.amd_instances > 0:
        findings.append(
            AuditFinding(
                code="EXTRA_AMD",
                severity="warn",
                message=(
                    f"{snapshot.amd_instances} AMD instance(s) present; "
                    "billing-safe profile uses 0 AMD"
                ),
                remediation="Terminate extra AMD instances in the OCI Console if staying at $0",
            )
        )

    if len(snapshot.arm_instances) > 1:
        findings.append(
            AuditFinding(
                code="EXTRA_ARM_INSTANCE",
                severity="warn",
                message=(
                    f"{len(snapshot.arm_instances)} ARM instances present; "
                    "billing-safe profile uses 1"
                ),
                remediation="Terminate unneeded ARM instances in the OCI Console",
            )
        )

    for arm in snapshot.arm_instances:
        if arm.ocpus > limits.max_arm_ocpus or arm.memory_gb > limits.max_arm_memory_gb:
            findings.append(
                AuditFinding(
                    code="LEGACY_ARM_SIZING",
                    severity="warn",
                    message=(
                        f"ARM instance '{arm.name or 'unknown'}' is {arm.ocpus} OCPU / "
                        f"{arm.memory_gb} GB (limit {limits.max_arm_ocpus}/"
                        f"{limits.max_arm_memory_gb})"
                    ),
                    remediation=resize_hint,
                )
            )

    total_storage = snapshot.boot_storage_gb + snapshot.block_storage_gb
    if total_storage > limits.max_storage_gb:
        findings.append(
            AuditFinding(
                code="STORAGE_OVER_CAP",
                severity="warn",
                message=(
                    f"Total storage {total_storage}GB exceeds "
                    f"{limits.max_storage_gb}GB Always Free limit"
                ),
                remediation="Delete or shrink block/boot volumes in the OCI Console",
            )
        )

    if snapshot.block_volume_count > 0:
        findings.append(
            AuditFinding(
                code="BLOCK_VOLUMES_PRESENT",
                severity="warn",
                message=(
                    f"{snapshot.block_volume_count} detached block volume(s) "
                    f"({snapshot.block_storage_gb}GB)"
                ),
                remediation="Delete unused block volumes in the OCI Console",
            )
        )

    if snapshot.vcn_count > limits.max_vcns:
        findings.append(
            AuditFinding(
                code="VCN_NEAR_LIMIT",
                severity="warn",
                message=(
                    f"{snapshot.vcn_count} VCN(s) present; "
                    f"Always Free limit is {limits.max_vcns}"
                ),
                remediation="Remove unused VCNs in the OCI Console",
            )
        )

    for shape in snapshot.non_free_shapes:
        findings.append(
            AuditFinding(
                code="NON_FREE_SHAPE",
                severity="warn",
                message=f"Non-free-tier compute shape in use: {shape}",
                remediation="Replace or terminate paid-shape instances to stay at $0",
            )
        )

    return findings


def validate_proposed_config(
    amd_instance_count: int,
    arm_instance_count: int,
    arm_ocpus_total: int,
    arm_memory_gb_total: int,
    total_storage_gb: int,
    *,
    billing_safe: bool = False,
    block_storage_gb: int = 0,
) -> list[str]:
    """Validate a proposed OCI Always Free configuration.

    Returns error strings; empty list means valid.
    When billing_safe=True, enforces viren070 profile (1× A1, 200 GB boot, no AMD).
    """
    errors: list[str] = []
    limits = LIMITS

    if amd_instance_count > limits.max_amd_instances:
        errors.append(
            f"ERROR: AMD instance count {amd_instance_count} exceeds limit {limits.max_amd_instances}"
        )
    if arm_instance_count > limits.max_arm_instances:
        errors.append(
            f"ERROR: ARM instance count {arm_instance_count} exceeds limit {limits.max_arm_instances}"
        )
    if arm_ocpus_total > limits.max_arm_ocpus:
        errors.append(
            f"ERROR: ARM OCPUs {arm_ocpus_total} exceed limit {limits.max_arm_ocpus}"
        )
    if arm_memory_gb_total > limits.max_arm_memory_gb:
        errors.append(
            f"ERROR: ARM memory {arm_memory_gb_total}GB exceeds limit {limits.max_arm_memory_gb}GB"
        )
    if total_storage_gb > limits.max_storage_gb:
        errors.append(
            f"ERROR: Total storage {total_storage_gb}GB exceeds limit {limits.max_storage_gb}GB"
        )

    if billing_safe:
        if amd_instance_count != 0:
            errors.append("ERROR: Billing-safe profile requires 0 AMD instances")
        if arm_instance_count != 1:
            errors.append("ERROR: Billing-safe profile requires exactly 1 ARM instance")
        if arm_ocpus_total != limits.default_arm_ocpus:
            errors.append(
                f"ERROR: Billing-safe profile requires {limits.default_arm_ocpus} ARM OCPUs"
            )
        if arm_memory_gb_total != limits.default_arm_memory_gb:
            errors.append(
                f"ERROR: Billing-safe profile requires {limits.default_arm_memory_gb}GB ARM memory"
            )
        if block_storage_gb > 0:
            errors.append("ERROR: Billing-safe profile requires no block volumes")
        if total_storage_gb != limits.default_boot_volume_gb:
            errors.append(
                f"ERROR: Billing-safe profile requires {limits.default_boot_volume_gb}GB boot only"
            )

    return errors
