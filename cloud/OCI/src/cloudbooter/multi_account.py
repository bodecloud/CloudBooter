"""Multi-account OCI resize orchestration via Bitwarden credentials."""
from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from cloudbooter.bitwarden import (
    OciBitwardenAccount,
    discover_oci_accounts,
    find_start_account_matches,
)
from cloudbooter.free_tier import TenancySnapshot, audit_tenancy, list_arm_resize_targets
from cloudbooter.oci_auth import (
    OciCredentialPaths,
    cleanup_credential_paths,
    materialize_oci_config,
)


@dataclass
class AccountRunResult:
    account: OciBitwardenAccount
    status: str
    error: str | None = None
    plan_type: str | None = None
    enforce_limits: bool | None = None
    inventory: dict[str, Any] | None = None
    resize_targets: list[dict[str, Any]] = field(default_factory=list)
    resize_outcomes: list[dict[str, Any]] = field(default_factory=list)
    audit_findings: list[dict[str, Any]] = field(default_factory=list)
    setup_exit_code: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "account": self.account.to_dict(),
            "status": self.status,
            "error": self.error,
            "plan_type": self.plan_type,
            "enforce_limits": self.enforce_limits,
            "inventory": self.inventory,
            "resize_targets": self.resize_targets,
            "resize_outcomes": self.resize_outcomes,
            "audit_findings": self.audit_findings,
            "setup_exit_code": self.setup_exit_code,
        }


@dataclass
class MigrationReport:
    generated_at: str
    start_account: str | None
    dry_run: bool
    processed: list[AccountRunResult] = field(default_factory=list)
    remaining: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "start_account": self.start_account,
            "dry_run": self.dry_run,
            "processed": [p.to_dict() for p in self.processed],
            "remaining": self.remaining,
        }


def _default_state_dir() -> Path:
    return Path(
        os.environ.get(
            "CLOUDBOOTER_OCI_STATE_DIR",
            Path.home() / ".cache" / "cloudbooter" / "oci",
        )
    )


def _default_report_dir() -> Path:
    return Path(
        os.environ.get(
            "CLOUDBOOTER_REPORT_DIR",
            Path(__file__).resolve().parents[2] / "reports",
        )
    )


def _oci_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _setup_script() -> Path:
    return _oci_root() / "setup_oci_terraform.sh"


def _load_report_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _build_remaining_entry(
    account: OciBitwardenAccount,
    *,
    status: str,
) -> dict[str, Any]:
    return {
        "slug": account.slug,
        "name": account.name,
        "username": account.username,
        "auth_mode": account.auth_mode,
        "missing_fields": list(account.missing_fields),
        "status": status,
    }


def run_setup_resize(
    paths: OciCredentialPaths,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Invoke setup_oci_terraform.sh in resize-only mode for one account."""
    env = os.environ.copy()
    env.update(
        {
            "NON_INTERACTIVE": "true",
            "AUTO_RESIZE_LEGACY_ARM": "true",
            "RESIZE_LEGACY_ARM_ONLY": "true",
            "ENFORCE_LIMITS": env.get("ENFORCE_LIMITS", "auto"),
            "OCI_CONFIG_FILE": str(paths.config_file),
            "OCI_PROFILE": paths.profile,
            "CLOUDBOOTER_REPORT_JSON": str(paths.state_dir / "report.json"),
        }
    )
    run = runner or subprocess.run
    return run(
        ["bash", str(_setup_script())],
        cwd=_oci_root(),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _enrich_from_report(result: AccountRunResult, report_path: Path) -> None:
    data = _load_report_json(report_path)
    if not data:
        return

    result.plan_type = data.get("plan_type")
    result.enforce_limits = data.get("enforce_limits")
    result.inventory = data.get("inventory")
    result.resize_outcomes = list(data.get("resize_outcomes") or [])

    if result.inventory:
        snapshot = TenancySnapshot.from_dict(result.inventory)
        result.resize_targets = list_arm_resize_targets(snapshot)
        result.audit_findings = [f.to_dict() for f in audit_tenancy(snapshot)]


def process_account(
    account: OciBitwardenAccount,
    *,
    state_root: Path,
    dry_run: bool = False,
    runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
) -> AccountRunResult:
    """Materialize auth and run resize workflow for one account."""
    if dry_run:
        return AccountRunResult(account=account, status="dry_run")

    if account.auth_mode != "api_key":
        return AccountRunResult(
            account=account,
            status="skipped",
            error=f"Credential not API-key ready ({account.auth_mode})",
        )

    paths: OciCredentialPaths | None = None
    try:
        paths = materialize_oci_config(account, state_root)
        proc = run_setup_resize(paths, runner=runner)
        result = AccountRunResult(
            account=account,
            status="processed" if proc.returncode == 0 else "failed",
            setup_exit_code=proc.returncode,
            error=(proc.stderr.strip() or None) if proc.returncode != 0 else None,
        )
        report_path = paths.state_dir / "report.json"
        _enrich_from_report(result, report_path)
        return result
    except Exception as exc:  # noqa: BLE001
        return AccountRunResult(
            account=account,
            status="failed",
            error=str(exc),
        )
    finally:
        if paths is not None:
            cleanup_credential_paths(paths)


def run_migration(
    *,
    start_account: str | None = None,
    account_filter: list[str] | None = None,
    dry_run: bool = False,
    session: str | None = None,
    state_root: Path | None = None,
    runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
    discover: Callable[..., list[OciBitwardenAccount]] | None = None,
) -> MigrationReport:
    """Discover BW accounts, process queue, and build migration report."""
    start = start_account or os.environ.get("BW_START_ACCOUNT")
    discover_fn = discover or discover_oci_accounts
    all_accounts = discover_fn(session=session, start_account=start)

    if start:
        matches = find_start_account_matches(all_accounts, start)
        if not matches:
            raise ValueError(
                f"No Bitwarden account matched start account '{start}'"
            )
        if len(matches) > 1:
            names = ", ".join(f"{m.name} ({m.username})" for m in matches)
            raise ValueError(
                f"Start account '{start}' matched multiple vault items: {names}"
            )

    if account_filter:
        needles = {a.lower() for a in account_filter}
        selected = [
            a
            for a in all_accounts
            if a.slug.lower() in needles
            or a.name.lower() in needles
            or a.username.lower() in needles
            or a.username.split("@", 1)[0].lower() in needles
        ]
        if not selected:
            raise ValueError(
                f"No accounts matched filter: {', '.join(account_filter)}"
            )
    else:
        selected = all_accounts

    state = state_root or _default_state_dir()
    report = MigrationReport(
        generated_at=datetime.now(timezone.utc).isoformat(),
        start_account=start,
        dry_run=dry_run,
    )

    processed_slugs = {a.slug for a in selected}
    for account in selected:
        result = process_account(
            account,
            state_root=state,
            dry_run=dry_run,
            runner=runner,
        )
        report.processed.append(result)

    for account in all_accounts:
        if account.slug in processed_slugs:
            continue
        report.remaining.append(_build_remaining_entry(account, status="pending"))

    for result in report.processed:
        if result.status == "skipped":
            report.remaining.append(
                _build_remaining_entry(result.account, status="skipped")
            )

    return report


def write_report_files(
    report: MigrationReport,
    report_dir: Path | None = None,
) -> tuple[Path, Path]:
    """Write JSON and markdown migration reports; return paths."""
    out_dir = report_dir or _default_report_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    json_path = out_dir / f"oci-bw-migration-{stamp}.json"
    md_path = out_dir / f"oci-bw-migration-{stamp}.md"

    json_path.write_text(
        json.dumps(report.to_dict(), indent=2),
        encoding="utf-8",
    )
    md_path.write_text(render_markdown_report(report), encoding="utf-8")
    return json_path, md_path


def render_markdown_report(report: MigrationReport) -> str:
    """Render a human-readable migration summary."""
    lines = [
        "# OCI Bitwarden Migration Report",
        "",
        f"- Generated: {report.generated_at}",
        f"- Start account: {report.start_account or '(none)'}",
        f"- Dry run: {report.dry_run}",
        "",
    ]

    if report.processed:
        lines.append("## Processed accounts")
        lines.append("")
        for item in report.processed:
            acct = item.account
            lines.append(f"### {acct.name} (`{acct.slug}`)")
            lines.append("")
            lines.append(f"- Username: {acct.username or '(none)'}")
            lines.append(f"- Status: {item.status}")
            if item.error:
                lines.append(f"- Error: {item.error}")
            if item.plan_type:
                lines.append(f"- Plan type: {item.plan_type}")
            if item.enforce_limits is not None:
                lines.append(f"- Enforce limits: {item.enforce_limits}")
            if item.inventory:
                inv = item.inventory
                lines.append(
                    f"- Inventory: {inv.get('amd_instances', 0)} AMD, "
                    f"{len(inv.get('arm_instances') or [])} ARM, "
                    f"boot {inv.get('boot_storage_gb', 0)} GB"
                )
            if item.resize_targets:
                lines.append("- Resize targets:")
                for t in item.resize_targets:
                    lines.append(
                        f"  - {t.get('name')}: {t.get('ocpus')} OCPU / "
                        f"{t.get('memory_gb')} GB → {t.get('target_ocpus')} / "
                        f"{t.get('target_memory_gb')} GB"
                    )
            if item.resize_outcomes:
                lines.append("- Resize outcomes:")
                for o in item.resize_outcomes:
                    status = "ok" if o.get("success") else "failed"
                    lines.append(
                        f"  - {o.get('name')} ({status}): "
                        f"{o.get('before_ocpus')}→{o.get('after_ocpus')} OCPU, "
                        f"{o.get('before_memory_gb')}→{o.get('after_memory_gb')} GB"
                    )
            if item.audit_findings:
                lines.append("- Audit findings:")
                for f in item.audit_findings:
                    lines.append(f"  - [{f.get('severity')}] {f.get('message')}")
            lines.append("")

    if report.remaining:
        lines.append("## Remaining accounts")
        lines.append("")
        lines.append("| Account | Username | Readiness | Status | Missing |")
        lines.append("|---------|----------|-----------|--------|---------|")
        for row in report.remaining:
            missing = ", ".join(row.get("missing_fields") or []) or "—"
            lines.append(
                f"| {row.get('name')} | {row.get('username') or '—'} | "
                f"{row.get('auth_mode')} | {row.get('status')} | {missing} |"
            )
        lines.append("")

    return "\n".join(lines)
