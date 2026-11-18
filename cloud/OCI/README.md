# CloudBooter for Oracle Cloud (OCI)

Scripts that set up a small Always Free-friendly stack in Oracle Cloud and write Terraform you can inspect before applying.

Oracle reduced Always Free A1 to **2 OCPU / 12 GB** in June 2026. The default profile stays billing-safe: one A1 instance and a 200 GB boot volume. See [docs/FREE_TIER_LIMITS.md](docs/FREE_TIER_LIMITS.md).

## Quick start

Linux / macOS / WSL:

```bash
cd cloud/OCI
./setup_oci_terraform.sh
```

Windows (PowerShell):

```powershell
cd cloud\OCI
.\setup_oci_terraform.ps1
```

Non-interactive, generate only:

```bash
NON_INTERACTIVE=true AUTO_DEPLOY=false ./setup_oci_terraform.sh
```

## Which script to use

| | Bash (`setup_oci_terraform.sh`) | PowerShell (`setup_oci_terraform.ps1`) |
|---|---|---|
| Best on | Linux, macOS, WSL | Native Windows (also works via `pwsh` elsewhere) |
| Needs | Bash 4+, `jq`, `curl` | PowerShell 5.1+ or PowerShell 7+ |
| Installs if missing | OCI CLI, Terraform | OCI CLI, Terraform |

Both scripts inventory resources, enforce free-tier checks, and generate Terraform. Bash retries capacity errors with bounded backoff; PowerShell stops after a failed apply so you can review a fresh plan.

## What the default profile creates

- VCN, public subnet, internet gateway, route table
- Security list with SSH ingress (optional extra ports)
- One Arm A1 instance: 2 OCPU / 12 GB, 200 GB boot @ 10 VPU (Balanced)
- ed25519 keys under `./ssh_keys/`
- `cloud-init.yaml` for basic first-boot setup

Optional **Maximum Free Tier** mode uses every available AMD + A1 slot. That can bill on PAYG accounts — read the warnings in [docs/FREE_TIER_LIMITS.md](docs/FREE_TIER_LIMITS.md) before using it.

## Docs

| Doc | What it covers |
|---|---|
| [USAGE.md](USAGE.md) | Commands, env vars, Bitwarden multi-account resize |
| [docs/QUICKSTART.md](docs/QUICKSTART.md) | First VM by console or script |
| [docs/OVERVIEW.md](docs/OVERVIEW.md) | How the OCI path works |
| [docs/FREE_TIER_LIMITS.md](docs/FREE_TIER_LIMITS.md) | Limits, PAYG safety, resize |

## Prerequisites

- An Oracle Cloud account (home region is fixed at signup)
- Internet access for OCI API calls
- For Bash: Bash 4+, `jq`, `curl`
- For PowerShell: PowerShell 5.1+ or 7+

Missing OCI CLI / Terraform are installed by the scripts when possible.

## Troubleshooting

**Session token expired**

```bash
oci session refresh --profile DEFAULT
```

**Out of capacity**

Always Free shapes can run out of host capacity. Wait and retry, request a smaller VM, or try another availability domain in your tenancy's home region when available. These steps do not guarantee capacity.

Bash retries capacity errors with bounded exponential backoff (`RETRY_MAX_ATTEMPTS`, `RETRY_BASE_DELAY`). PowerShell stops after a failed apply because some resources may already exist: run **Plan only**, review the updated changes, then choose **Deploy** to create and confirm a fresh plan.

**PowerShell blocked scripts**

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

## See also

- [Root README](../../README.md)
- [Oracle Always Free](https://www.oracle.com/cloud/free/)
- [OCI CLI docs](https://docs.oracle.com/en-us/iaas/Content/API/Concepts/cliconcepts.htm)
- [Terraform OCI provider](https://registry.terraform.io/providers/oracle/oci/latest/docs)
