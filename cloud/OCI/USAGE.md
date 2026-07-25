# OCI usage

Command reference for the Oracle Cloud bootstrap scripts and the Bitwarden multi-account resize helper.

Always Free A1 is **2 OCPU / 12 GB** as of June 2026. See [docs/FREE_TIER_LIMITS.md](docs/FREE_TIER_LIMITS.md).

## Scripts

| Script | Platform |
|---|---|
| [`setup_oci_terraform.sh`](setup_oci_terraform.sh) | Linux, macOS, WSL |
| [`setup_oci_terraform.ps1`](setup_oci_terraform.ps1) | Windows (also via `pwsh`) |
| [`bw_oci_resize_all.sh`](bw_oci_resize_all.sh) | Bitwarden-driven legacy ARM resize across accounts |

## Interactive menu

When you run `setup_oci_terraform.sh` interactively, the plan menu offers:

1. Use existing instances
2. Use saved `variables.tf`
3. Custom new instances
4. **Recommended (billing-safe)** — 1× A1 (2/12), 200 GB boot — default
5. Maximum Free Tier — all AMD + A1 (**PAYG warning**)

`NON_INTERACTIVE=true` selects option 4.

When strict limits are on (PAYG tenancy or `ENFORCE_LIMITS=true`), option 5 and over-cap custom plans are rejected. Apply only runs if the proposed config is billing-safe.

Legacy ARM instances above 2/12 are resized automatically when `NON_INTERACTIVE=true` (or when `AUTO_RESIZE_LEGACY_ARM=true`). Use `RESIZE_LEGACY_ARM_ONLY=true` to resize and exit.

## Environment variables

| Variable | Description | Default |
|---|---|---|
| `ENFORCE_LIMITS` | Billing-safe enforcement: `auto`, `true`, or `false` | `auto` |
| `AUTO_RESIZE_LEGACY_ARM` | Downsize legacy ARM: `auto`, `true`, or `false` | `auto` |
| `RESIZE_LEGACY_ARM_ONLY` | Auth, inventory, resize, then exit | `false` |
| `NON_INTERACTIVE` | Skip prompts | `false` |
| `AUTO_USE_EXISTING` | Prefer existing instances (menu option 1) | `false` |
| `AUTO_DEPLOY` | Run Terraform apply after generation | `false` |
| `SKIP_CONFIG` | Skip config prompts; load existing or defaults | `false` |
| `FORCE_REAUTH` | Force browser re-authentication | `false` |
| `OCI_PROFILE` | OCI CLI profile name | `DEFAULT` |
| `OCI_AUTH_REGION` | Skip region selection | (prompt) |
| `RETRY_MAX_ATTEMPTS` | Capacity retry count | `8` |
| `RETRY_BASE_DELAY` | Retry backoff base in seconds | `15` |
| `DEBUG` | Verbose output | `false` |
| `OPEN_ALL_PORTS` | Open all ingress on the security list — **high risk**, last resort only | `false` |
| `EXTRA_INGRESS_PORTS` | Extra TCP ports, comma-separated (for example `443,80`) | (none) |
| `TF_BACKEND` | `local` or `oci` remote state | `local` |
| `TF_BACKEND_BUCKET` | OCI Object Storage bucket when `TF_BACKEND=oci` | (none) |

Examples:

```bash
NON_INTERACTIVE=true AUTO_DEPLOY=false ./setup_oci_terraform.sh
OCI_PROFILE=MyProfile FORCE_REAUTH=true ./setup_oci_terraform.sh
RESIZE_LEGACY_ARM_ONLY=true ./setup_oci_terraform.sh
```

```powershell
$env:NON_INTERACTIVE = 'true'
$env:AUTO_DEPLOY = 'false'
.\setup_oci_terraform.ps1
```

## Bitwarden multi-account resize

Discovers Oracle Cloud logins in Bitwarden, authenticates with API-key custom fields, and runs the resize-only workflow per account.

**Needs:** Bitwarden CLI (`npm i -g @bitwarden/cli`), an unlocked vault **or** an offline export, OCI CLI, and `jq`.

**Security:** Never paste vault exports, session keys, or PEM material into chat or issues. Reports may include tenancy OCIDs — treat them as sensitive.

Offline / agent-friendly workflow:

```bash
# Human terminal (once)
mkdir -p ~/.cache/cloudbooter
bw unlock --raw > ~/.cache/cloudbooter/bw-session
chmod 600 ~/.cache/cloudbooter/bw-session
./export_bw_items.sh   # writes cloud/OCI/.bw-items.json (mode 0600)
```

```bash
export BW_SESSION=$(bw unlock --raw)
export BW_START_ACCOUNT=acct-01   # optional; processed first when set

# Dry run — classify vault items, no OCI changes
./bw_oci_resize_all.sh --dry-run --start-account acct-01

# Single account
./bw_oci_resize_all.sh --start-account acct-01 --accounts acct-01

# Full queue
./bw_oci_resize_all.sh
```

Reports land in `reports/oci-bw-migration-<timestamp>.{json,md}` (override with `CLOUDBOOTER_REPORT_DIR`). Migration reports are gitignored.

Bitwarden items should include custom fields: `tenancy_ocid`, `user_ocid`, `fingerprint`, `region`, `private_key` (PEM). Console-only entries are skipped.

Python CLI equivalents:

```bash
python -m cloudbooter.cli bw-list-accounts --json
python -m cloudbooter.cli bw-resize-all --dry-run --start-account acct-01 --json
```

| Variable | Description | Default |
|---|---|---|
| `BW_SESSION` | Bitwarden vault session key | required for live vault |
| `BW_SESSION_FILE` | Path to session key file | `~/.cache/cloudbooter/bw-session` |
| `BW_ITEMS_FILE` | Offline vault export JSON | `cloud/OCI/.bw-items.json` |
| `BW_START_ACCOUNT` | Account slug to run first | (none) |
| `CLOUDBOOTER_OCI_STATE_DIR` | Temp OCI config / key material | `~/.cache/cloudbooter/oci` |
| `CLOUDBOOTER_REPORT_DIR` | Report output directory | `reports/` |

## More docs

- [docs/QUICKSTART.md](docs/QUICKSTART.md)
- [docs/FREE_TIER_LIMITS.md](docs/FREE_TIER_LIMITS.md)
- [docs/OVERVIEW.md](docs/OVERVIEW.md)
- [README.md](README.md)
