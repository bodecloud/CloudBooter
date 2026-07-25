# GCP quick start

## Prerequisites

- A GCP project with an active billing account (required even for Always Free)
- Python 3.11+ and/or the `gcloud` CLI
- Terraform 1.6+ (the setup script installs it when it can)

## First run

```bash
git clone git@github.com:bodecloud/CloudBooter.git
cd CloudBooter/cloud/GCP

export GCP_PROJECT_ID="my-gcp-project"
./setup_gcp_terraform.sh
```

The script will:

1. Install `gcloud` / Terraform if needed (or fall back to Python SDK mode)
2. Walk you through auth if ADC is missing
3. Inventory existing resources
4. Prompt for region / zone / instance name (or use defaults)
5. Generate Terraform
6. Ask before `terraform apply`

Windows:

```powershell
$env:GCP_PROJECT_ID = "my-gcp-project"
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\setup_gcp_terraform.ps1
```

## Non-interactive

```bash
export GCP_PROJECT_ID="my-proj"
export GCP_CREDENTIALS_FILE="/path/to/sa-key.json"
export NON_INTERACTIVE=true
export AUTO_DEPLOY=false
./setup_gcp_terraform.sh
```

## Python CLI

```bash
pip install -e .
cloudbooter-gcp deploy --project my-proj --region us-central1
cloudbooter-gcp validate --project my-proj --disk-gb 20
cloudbooter-gcp inventory --project my-proj
```

## After apply

Terraform prints the external IP and an SSH command. Default key path is `~/.ssh/cloudbooter_gcp` unless you set `GCP_SSH_KEY_FILE`.

## Teardown

```bash
terraform destroy -var="project_id=my-proj"
```

More detail: [USAGE.md](../USAGE.md), [FREE_TIER_LIMITS.md](FREE_TIER_LIMITS.md).
