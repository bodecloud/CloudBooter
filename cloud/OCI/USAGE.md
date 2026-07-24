# CloudBooter OCI — Usage

Command-line usage and environment variables for the Oracle Cloud bootstrap scripts.

> **Always Free A1 resources reduced (June 2026)** — current allowance is **2 OCPU / 12 GB** for `VM.Standard.A1.Flex`. See [docs/FREE_TIER_LIMITS.md](docs/FREE_TIER_LIMITS.md) for disclaimers and PAYG billing safety.

## Scripts

| Script | Platform |
|--------|----------|
| [`setup_oci_terraform.sh`](setup_oci_terraform.sh) | Linux, macOS, WSL |
| [`setup_oci_terraform.ps1`](setup_oci_terraform.ps1) | Windows (TUI), cross-platform via `pwsh` |
| [`bw_oci_resize_all.sh`](bw_oci_resize_all.sh) | Bitwarden multi-account legacy ARM resize |

## Bitwarden multi-account resize

Discover OCI accounts from Bitwarden (`cloud.oracle.com` logins), authenticate via API-key custom fields, and run the resize-only workflow per account.

**Prerequisites:** Bitwarden CLI (`npm i -g @bitwarden/cli`), unlocked vault **or** offline export, OCI CLI, `jq`.

**Security:** Never paste vault exports, session keys, or PEM material into chat. Reports may contain tenancy OCIDs but not secrets.

**Offline / agent workflow:**

```bash
# Human terminal (once)
mkdir -p ~/.cache/cloudbooter
bw unlock --raw > ~/.cache/cloudbooter/bw-session
chmod 600 ~/.cache/cloudbooter/bw-session
./export_bw_items.sh   # writes cloud/OCI/.bw-items.json (0600)
```

Then the agent can run dry-run/live without live vault unlock if `.bw-items.json` exists.

```bash
export BW_SESSION=$(bw unlock --raw)
export BW_START_ACCOUNT=armandfcrouch   # optional; processed first when set

# Dry run (classify vault items, no OCI changes)
./bw_oci_resize_all.sh --dry-run --start-account armandfcrouch

# Single account
./bw_oci_resize_all.sh --start-account armandfcrouch --accounts armandfcrouch

# Full queue
./bw_oci_resize_all.sh
```

Reports are written to `reports/oci-bw-migration-<timestamp>.{json,md}` (override with `CLOUDBOOTER_REPORT_DIR`).

Bitwarden items should include custom fields: `tenancy_ocid`, `user_ocid`, `fingerprint`, `region`, `private_key` (PEM). Console-only entries are listed as skipped.

Python CLI equivalents:

```bash
python -m cloudbooter.cli bw-list-accounts --json
python -m cloudbooter.cli bw-resize-all --dry-run --start-account armandfcrouch --json
```

| Variable | Description | Default |
|----------|-------------|---------|
| `BW_SESSION` | Bitwarden vault session key | (required for live vault) |
| `BW_SESSION_FILE` | Path to session key file | `~/.cache/cloudbooter/bw-session` |
| `BW_ITEMS_FILE` | Offline vault export JSON | `cloud/OCI/.bw-items.json` |
| `BW_START_ACCOUNT` | Account slug/username to run first | (none) |
| `CLOUDBOOTER_OCI_STATE_DIR` | Temp OCI config/key material | `~/.cache/cloudbooter/oci` |
| `CLOUDBOOTER_REPORT_DIR` | Migration report output directory | `reports/` |
| `CLOUDBOOTER_REPORT_JSON` | Per-account report path (set by orchestrator) | (none) |

## Interactive setup menu

When running `setup_oci_terraform.sh` interactively, the instance plan menu offers:

1. Use existing instances  
2. Use saved `variables.tf`  
3. Custom new instances  
4. **Recommended (billing-safe)** — 1× A1 (2/12), 200 GB boot **[default]**  
5. Maximum Free Tier — all AMD + A1 (**PAYG warning**)

Non-interactive mode (`NON_INTERACTIVE=true`) selects option 4.

When strict limits are active (PAYG tenancy or `ENFORCE_LIMITS=true`), option 5 and over-cap custom configs are rejected; apply requires a billing-safe proposed configuration.

Legacy ARM instances above 2/12 are auto-resized when `NON_INTERACTIVE=true` (or set `AUTO_RESIZE_LEGACY_ARM=true`). Use `RESIZE_LEGACY_ARM_ONLY=true` to resize only.

## Environment variables

| Variable | Description | Default |
|----------|-------------|---------|
| `AUTO_RESIZE_LEGACY_ARM` | Downsize legacy ARM: `auto`, `true`, or `false` | `auto` |
| `RESIZE_LEGACY_ARM_ONLY` | Auth, inventory, resize, then exit | `false` |
| `ENFORCE_LIMITS` | Billing-safe enforcement: `auto`, `true`, or `false` | `auto` |
| `NON_INTERACTIVE` | Skip prompts | `false` |
| `AUTO_USE_EXISTING` | Prefer existing instances (menu option 1) | `false` |
| `AUTO_DEPLOY` | Run Terraform apply after generation | `false` |
| `SKIP_CONFIG` | Skip configuration; load existing or defaults | `false` |
| `FORCE_REAUTH` | Force browser re-authentication | `false` |
| `OCI_PROFILE` | OCI CLI profile name | `DEFAULT` |
| `OCI_AUTH_REGION` | Skip region selection | (prompt) |
| `RETRY_MAX_ATTEMPTS` | Capacity retry count | `8` |
| `RETRY_BASE_DELAY` | Retry backoff base (seconds) | `15` |
| `DEBUG` | Verbose output | `false` |
| `OPEN_ALL_PORTS` | Open all ingress on security list | `false` |
| `EXTRA_INGRESS_PORTS` | Comma-separated TCP ports (e.g. `443,80`) | (none) |
| `TF_BACKEND` | `local` or `oci` remote state | `local` |

## Documentation

- [docs/QUICKSTART.md](docs/QUICKSTART.md) — console walkthrough  
- [docs/FREE_TIER_LIMITS.md](docs/FREE_TIER_LIMITS.md) — limits, maximization, PAYG  
- [docs/OVERVIEW.md](docs/OVERVIEW.md) — comprehensive guide  
- [README.md](README.md) — provider overview  
