"""CloudBooter OCI — free-tier constants and validation."""

from cloudbooter.bitwarden import OciBitwardenAccount, discover_oci_accounts
from cloudbooter.multi_account import MigrationReport, run_migration
from cloudbooter.oci_auth import OciCredentialPaths, materialize_oci_config
from cloudbooter.free_tier import (
    LIMITS,
    OCIFreeTierLimits,
    ArmInstanceSnapshot,
    AuditFinding,
    TenancySnapshot,
    arm_instance_needs_resize,
    audit_tenancy,
    list_arm_resize_targets,
    resolve_enforce_limits,
    should_auto_resize_legacy_arm,
    validate_proposed_config,
)

__all__ = [
    "MigrationReport",
    "OciBitwardenAccount",
    "OciCredentialPaths",
    "discover_oci_accounts",
    "materialize_oci_config",
    "run_migration",
    "LIMITS",
    "OCIFreeTierLimits",
    "ArmInstanceSnapshot",
    "AuditFinding",
    "TenancySnapshot",
    "arm_instance_needs_resize",
    "audit_tenancy",
    "list_arm_resize_targets",
    "resolve_enforce_limits",
    "should_auto_resize_legacy_arm",
    "validate_proposed_config",
]
