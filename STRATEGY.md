---
name: CloudBooter
last_updated: 2026-07-24
---

# CloudBooter Strategy

## Target problem

Beginners and operators with multiple cloud accounts cannot safely stay inside Always Free limits after provider policy changes (e.g. OCI A1 reduced to 2 OCPU / 12 GB in June 2026). Manual console checks do not scale across tenancies, and PAYG accounts silently bill when legacy resources remain over cap.

## Our approach

Terminal-first, inspect-before-apply bootstrap: inventory what exists, enforce billing-safe caps in non-interactive paths, and resize or block provisioning before Terraform apply — with credentials sourced from the operator's vault or explicit env, never hardcoded.

## Who it's for

**Primary:** Homelab operator — They're hiring CloudBooter to keep several Oracle (and future GCP / Cloudflare) accounts inside Always Free / free-plan limits without living in the console.

**Secondary:** Maintainer — They're hiring CloudBooter to encode policy (strict limits, resize-only fast paths) as repeatable scripts and tests.

## Key metrics

- **Tenancies audit-clean after run** — Count of accounts with zero blocking audit findings post-resize; measured from `cloudbooter.cli audit` / migration JSON reports
- **Legacy ARM instances at 2/12** — A1 instances still above billing-safe shape after orchestrator run; from resize outcomes in reports
- **Blocked unsafe applies** — Terraform apply attempts rejected when strict limits active; from setup script exit codes in CI or logs

## Tracks

### OCI billing-safe automation

Inventory, strict limits, legacy ARM resize, Bitwarden multi-account orchestration, and session/API-key auth paths.

_Why it serves the approach:_ OCI is the only fully implemented provider and the immediate PAYG risk surface.

### Multi-cloud scaffold

GCP and Cloudflare scaffolds and shared Python patterns (`free_tier`, CLI hooks) portable across providers.

_Why it serves the approach:_ Keeps the billing-safe pattern reusable instead of one-off bash per cloud.

### Credential discovery and auth

Bitwarden discovery, offline export, cloud account name vs vault slug, console session auth fallback.

_Why it serves the approach:_ Resize cannot run without reliable, non-interactive auth across many accounts.

## Not working on

- One-click production platforms or managed hosting
- Creating API keys inside customer consoles during batch runs
- Storing or committing secrets in the repository

## Marketing

**One-liner:** CloudBooter helps you bootstrap cloud infrastructure from the terminal with billing-safe defaults and inspect-before-apply Terraform.

**Key message:** Start from what you already have, see the plan, then apply — with Always Free enforcement built in for Oracle Cloud today.
