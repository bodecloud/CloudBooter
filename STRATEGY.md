---
name: CloudBooter
last_updated: 2026-07-24
---

# CloudBooter strategy

## Problem

People who run several free-tier cloud accounts cannot keep them inside current limits by clicking around the console. Provider rules change (Oracle cut Always Free A1 to 2 OCPU / 12 GB in June 2026). Pay-as-you-go accounts quietly bill when leftover resources sit over the free caps.

## Approach

Terminal-first, inspect-before-apply:

- Inventory what already exists.
- Enforce billing-safe caps on non-interactive paths.
- Resize or block unsafe plans before `terraform apply`.
- Pull credentials from the operator's vault or explicit environment variables — never hardcode them in the repo.

## Who it is for

- Homelab operators who want several Oracle (and later GCP / Cloudflare) accounts to stay inside free limits without living in the console.
- Maintainers who want those rules encoded as scripts and tests instead of tribal knowledge.

## Work tracks

### OCI billing-safe automation

Inventory, strict limits, legacy ARM resize, Bitwarden multi-account orchestration, and session / API-key auth. OCI is the only fully implemented provider and the place where PAYG risk shows up first.

### Multi-cloud scaffold

GCP and Cloudflare share the same Python patterns (`free_tier`, CLI hooks) so the billing-safe idea is reusable instead of one-off bash per cloud.

### Credential discovery

Bitwarden discovery, offline export, matching cloud account names to vault items, and console session auth as a fallback. Resize across many accounts does not work without reliable non-interactive auth.

## Out of scope

- One-click production platforms or managed hosting
- Creating API keys inside customer consoles during batch runs
- Storing or committing secrets in this repository
