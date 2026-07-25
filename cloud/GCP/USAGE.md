# GCP usage

Entrypoints, environment variables, and auth notes for the Google Cloud scaffold.

## Entrypoints

| Entrypoint | Platform |
|---|---|
| `./setup_gcp_terraform.sh` | Linux / macOS / WSL |
| `.\setup_gcp_terraform.ps1` | Windows |
| `cloudbooter-gcp` / `python -m cloudbooter` | All (Click CLI after `pip install -e .`) |

## CLI

```bash
cd cloud/GCP
pip install -e .

cloudbooter-gcp deploy --project my-proj --region us-central1
cloudbooter-gcp validate --project my-proj --region us-central1 --disk-gb 20
cloudbooter-gcp inventory --project my-proj --region us-central1
cloudbooter-gcp install-deps
```

## Environment variables

### GCP-specific

| Variable | Purpose | Default |
|---|---|---|
| `GCP_PROJECT_ID` | Project ID | required |
| `GCP_REGION` | Compute region | `us-central1` |
| `GCP_ZONE` | Compute zone | auto / `us-central1-a` |
| `GCP_INSTANCE_NAME` | Instance name | `cloudbooter-vm` |
| `GCP_BOOT_DISK_GB` | Boot disk size (max 30 for free) | `20` |
| `GCP_CREDENTIALS_FILE` | SA key or WIF JSON path | (none) |
| `GCP_IMPERSONATE_SA` | Impersonate SA email (Bash / PowerShell scripts) | (none) |
| `GCP_IMPERSONATE_SERVICE_ACCOUNT` | Impersonate SA email (Python CLI) | (none) |
| `GCP_SSH_KEY_FILE` | SSH key path; generated if missing | `~/.ssh/cloudbooter_gcp` |
| `GCP_SSH_PUBLIC_KEY` | Public key string or `@path` (CLI) | (none) |
| `GCP_ALLOW_PAID_RESOURCES` | Bypass free-tier guards | `false` |
| `GCP_MODE` | `gcloud` or `python` (SDK fallback) | `gcloud` |
| `TF_BACKEND` | `local` or `gcs` | `local` |
| `TF_BACKEND_BUCKET` | GCS bucket when `TF_BACKEND=gcs` | (none) |

Known mismatch: the setup scripts read `GCP_IMPERSONATE_SA`, while the Python CLI reads `GCP_IMPERSONATE_SERVICE_ACCOUNT`. Set both if you use impersonation from mixed entrypoints until that is unified.

### Shared

| Variable | Purpose | Default |
|---|---|---|
| `NON_INTERACTIVE` | No prompts | `false` |
| `AUTO_USE_EXISTING` | Prefer discovered resources | `false` |
| `AUTO_DEPLOY` | Run `terraform apply` after generate | `false` |
| `SKIP_CONFIG` | Skip config prompts | `false` |
| `DEBUG` | Verbose shell tracing | `false` |
| `FORCE_REAUTH` | Force re-auth | `false` |
| `RETRY_MAX_ATTEMPTS` | Apply retries | `8` |
| `RETRY_BASE_DELAY` | Backoff base seconds | `15` |

## Auth

Precedence used by the toolkit:

1. `GCP_CREDENTIALS_FILE` pointing at a service-account or WIF JSON
2. Impersonation (`GCP_IMPERSONATE_SA` / `GCP_IMPERSONATE_SERVICE_ACCOUNT`)
3. Application Default Credentials (`gcloud auth application-default login` or metadata server)

Interactive runs prefer `gcloud`. If the SDK cannot be installed, the Bash script falls back to `GCP_MODE=python`.

Non-interactive example:

```bash
GCP_PROJECT_ID=my-proj \
GCP_CREDENTIALS_FILE=/path/to/sa-key.json \
NON_INTERACTIVE=true \
AUTO_DEPLOY=false \
./setup_gcp_terraform.sh
```

## Generated files

Typically: `provider.tf`, `variables.tf`, `data_sources.tf`, `main.tf`, `cloud-init.yaml`. Do not commit credentials into the output directory.

## Safety

Always review `terraform plan`. Reserved but unattached static external IPs bill. Cloud DNS, Cloud NAT, and load balancers are not free — CloudBooter warns or blocks them unless you allow paid resources.

## More docs

- [README.md](README.md)
- [docs/QUICKSTART.md](docs/QUICKSTART.md)
- [docs/OVERVIEW.md](docs/OVERVIEW.md)
- [docs/FREE_TIER_LIMITS.md](docs/FREE_TIER_LIMITS.md)
