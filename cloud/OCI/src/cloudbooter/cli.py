"""CLI for OCI free-tier audit and validation (invoked by setup scripts)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from cloudbooter.bitwarden import (
    default_items_file,
    discover_oci_accounts,
    discover_oci_accounts_from_items,
    load_items_file,
)
from cloudbooter.free_tier import (
    TenancySnapshot,
    audit_tenancy,
    list_arm_resize_targets,
    resolve_enforce_limits,
    should_auto_resize_legacy_arm,
    validate_proposed_config,
)
from cloudbooter.multi_account import run_migration, write_report_files


def _load_json_stdin() -> dict[str, Any]:
    if sys.stdin.isatty():
        return {}
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    return json.loads(raw)


def cmd_audit(args: argparse.Namespace) -> int:
    data = _load_json_stdin()
    snapshot = TenancySnapshot.from_dict(data)
    findings = audit_tenancy(snapshot)

    if args.json:
        print(json.dumps([f.to_dict() for f in findings], indent=2))
    else:
        for finding in findings:
            prefix = finding.severity.upper()
            line = f"[{prefix}] {finding.message}"
            if finding.remediation:
                line += f" — {finding.remediation}"
            print(line)

    blocking = [f for f in findings if f.severity == "error"]
    return 1 if blocking else 0


def cmd_resolve_enforce(args: argparse.Namespace) -> int:
    active = resolve_enforce_limits(args.plan_type, args.env_value)
    if args.json:
        print(json.dumps({"enforce_limits": active}))
    else:
        print("true" if active else "false")
    return 0


def cmd_resize_candidates(args: argparse.Namespace) -> int:
    data = _load_json_stdin()
    snapshot = TenancySnapshot.from_dict(data)
    targets = list_arm_resize_targets(snapshot)
    print(json.dumps(targets, indent=2))
    return 0


def cmd_should_auto_resize(args: argparse.Namespace) -> int:
    active = should_auto_resize_legacy_arm(
        args.env_value,
        non_interactive=args.non_interactive,
        resize_only=args.resize_only,
    )
    if args.json:
        print(json.dumps({"auto_resize": active}))
    else:
        print("true" if active else "false")
    return 0


def _discover_accounts(args: argparse.Namespace) -> list:
    if args.items_file:
        items = load_items_file(args.items_file)
        return discover_oci_accounts_from_items(
            items, start_account=args.start_account
        )
    default_file = default_items_file()
    if default_file.is_file() and default_file.stat().st_size > 0:
        import datetime

        age_hours = (
            datetime.datetime.now().timestamp() - default_file.stat().st_mtime
        ) / 3600
        if age_hours > 24:
            print(
                f"Warning: using offline export {default_file} ({age_hours:.0f}h old). "
                "Re-run ./export_bw_items.sh for fresh vault data.",
                file=sys.stderr,
            )
        items = load_items_file(default_file)
        return discover_oci_accounts_from_items(
            items, start_account=args.start_account
        )
    return discover_oci_accounts(
        session=args.session,
        start_account=args.start_account,
    )


def cmd_bw_list_accounts(args: argparse.Namespace) -> int:
    try:
        accounts = _discover_accounts(args)
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    payload = [a.to_dict() for a in accounts]
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        for acct in accounts:
            print(
                f"{acct.slug}\t{acct.name}\t{acct.username}\t"
                f"{acct.auth_mode}\tmissing={','.join(acct.missing_fields) or '-'}"
            )
    return 0


def cmd_bw_resize_all(args: argparse.Namespace) -> int:
    account_filter = args.accounts or None

    def discover(**_kwargs):
        return _discover_accounts(args)

    try:
        report = run_migration(
            start_account=args.start_account,
            account_filter=account_filter,
            dry_run=args.dry_run,
            session=args.session,
            discover=discover,
        )
        json_path, md_path = write_report_files(report, report_dir=args.report_dir)
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.json:
        payload = report.to_dict()
        payload["report_json"] = str(json_path)
        payload["report_markdown"] = str(md_path)
        print(json.dumps(payload, indent=2))
    else:
        print(f"Report JSON: {json_path}")
        print(f"Report markdown: {md_path}")
        failed = [p for p in report.processed if p.status == "failed"]
        if failed:
            return 1
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    data = _load_json_stdin()
    errors = validate_proposed_config(
        int(data.get("amd_instances", 0)),
        int(data.get("arm_instances", 0)),
        int(data.get("arm_ocpus_total", 0)),
        int(data.get("arm_memory_gb_total", 0)),
        int(data.get("total_storage_gb", 0)),
        billing_safe=bool(data.get("billing_safe", False)),
        block_storage_gb=int(data.get("block_storage_gb", 0)),
    )

    if args.json:
        print(json.dumps({"valid": not errors, "errors": errors}, indent=2))
    else:
        for err in errors:
            print(err)

    return 1 if errors else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cloudbooter.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    audit_parser = sub.add_parser("audit", help="Audit tenancy inventory snapshot")
    audit_parser.add_argument(
        "--stdin-json",
        action="store_true",
        help="Read TenancySnapshot JSON from stdin",
    )
    audit_parser.add_argument("--json", action="store_true", help="Emit JSON findings")
    audit_parser.set_defaults(func=cmd_audit)

    resolve_parser = sub.add_parser(
        "resolve-enforce", help="Resolve ENFORCE_LIMITS from plan type and env"
    )
    resolve_parser.add_argument(
        "--plan-type",
        default="unknown",
        help="Subscription plan_type (PAYG, FREE_TIER, unknown)",
    )
    resolve_parser.add_argument(
        "--env-value",
        default="auto",
        help="ENFORCE_LIMITS env value (auto, true, false)",
    )
    resolve_parser.add_argument("--json", action="store_true")
    resolve_parser.set_defaults(func=cmd_resolve_enforce)

    validate_parser = sub.add_parser("validate", help="Validate proposed configuration")
    validate_parser.add_argument(
        "--stdin-json",
        action="store_true",
        help="Read proposed config JSON from stdin",
    )
    validate_parser.add_argument("--json", action="store_true")
    validate_parser.set_defaults(func=cmd_validate)

    resize_parser = sub.add_parser(
        "resize-candidates", help="List ARM instances needing downsize to 2/12"
    )
    resize_parser.add_argument("--stdin-json", action="store_true")
    resize_parser.set_defaults(func=cmd_resize_candidates)

    auto_resize_parser = sub.add_parser(
        "should-auto-resize", help="Resolve AUTO_RESIZE_LEGACY_ARM behavior"
    )
    auto_resize_parser.add_argument("--env-value", default="auto")
    auto_resize_parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="NON_INTERACTIVE=true was set",
    )
    auto_resize_parser.add_argument(
        "--resize-only",
        action="store_true",
        help="RESIZE_LEGACY_ARM_ONLY=true was set",
    )
    auto_resize_parser.add_argument("--json", action="store_true")
    auto_resize_parser.set_defaults(func=cmd_should_auto_resize)

    bw_list_parser = sub.add_parser(
        "bw-list-accounts", help="Discover OCI accounts in Bitwarden vault"
    )
    bw_list_parser.add_argument(
        "--start-account",
        default=None,
        help="Account slug/username to sort first (default: BW_START_ACCOUNT env)",
    )
    bw_list_parser.add_argument(
        "--session",
        default=None,
        help="Bitwarden session key (default: BW_SESSION env)",
    )
    bw_list_parser.add_argument(
        "--items-file",
        type=Path,
        default=None,
        help="Offline bw list items JSON export (skips live vault unlock)",
    )
    bw_list_parser.add_argument("--json", action="store_true")
    bw_list_parser.set_defaults(func=cmd_bw_list_accounts)

    bw_resize_parser = sub.add_parser(
        "bw-resize-all",
        help="Run resize-only workflow for Bitwarden OCI accounts",
    )
    bw_resize_parser.add_argument(
        "--start-account",
        default=None,
        help="Process this account first (default: BW_START_ACCOUNT env)",
    )
    bw_resize_parser.add_argument(
        "--accounts",
        nargs="+",
        default=None,
        help="Limit processing to these account slugs/usernames",
    )
    bw_resize_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Discover and classify accounts without OCI changes",
    )
    bw_resize_parser.add_argument(
        "--session",
        default=None,
        help="Bitwarden session key (default: BW_SESSION env)",
    )
    bw_resize_parser.add_argument(
        "--report-dir",
        type=Path,
        default=None,
        help="Directory for migration reports",
    )
    bw_resize_parser.add_argument(
        "--items-file",
        type=Path,
        default=None,
        help="Offline bw list items JSON export (skips live vault unlock)",
    )
    bw_resize_parser.add_argument("--json", action="store_true")
    bw_resize_parser.set_defaults(func=cmd_bw_resize_all)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
