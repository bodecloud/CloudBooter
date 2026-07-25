# CloudBooter for Google Cloud (GCP)

Sets up a small Always Free-friendly Compute Engine layout and writes Terraform you can inspect before applying.

GCP still requires a billing account even for Always Free usage. The free compute allowance is **744 `e2-micro` hours per month** in three US regions — enough for one instance running all month, not a blank check.

## Quick start

```bash
export GCP_PROJECT_ID="my-project"
cd cloud/GCP
./setup_gcp_terraform.sh
```

Windows: `.\setup_gcp_terraform.ps1`

Full walkthrough: [docs/QUICKSTART.md](docs/QUICKSTART.md). Commands and env vars: [USAGE.md](USAGE.md).

## What the default creates

| Resource | Type | Free allowance? |
|---|---|---|
| VPC | `google_compute_network` | Yes |
| Subnet | `google_compute_subnetwork` | Yes |
| SSH + ICMP firewall rules | `google_compute_firewall` | Yes (logging off) |
| Boot disk ≤ 30 GB `pd-standard` | `google_compute_disk` | Yes |
| `e2-micro` in `us-central1` / `us-west1` / `us-east1` | `google_compute_instance` | Yes within 744 h/month |

## Guardrails

Three layers, same idea as OCI:

1. Bash / PowerShell constants before generation
2. Python `GCPFreeTierLimits` for the CLI and tests
3. Terraform `check` blocks at plan / apply time

Override only with `GCP_ALLOW_PAID_RESOURCES=true`. Numbers: [docs/FREE_TIER_LIMITS.md](docs/FREE_TIER_LIMITS.md).

## Layout

```text
cloud/GCP/
├── setup_gcp_terraform.sh
├── setup_gcp_terraform.ps1
├── src/cloudbooter/     # free_tier, renderers, auth, inventory, CLI
├── tests/
└── docs/
```

## Tests

```bash
cd cloud/GCP
pip install -e ".[dev]"   # or: pip install -r requirements.txt && pip install -e .
pytest
```

Live-project tests skip unless credentials and a project are present. Tests that need `terraform` on `PATH` skip when it is missing.

## License

MIT — see the root [LICENSE](../../LICENSE).
