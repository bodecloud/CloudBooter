# GCP Always Free limits

Limits CloudBooter enforces for the GCP scaffold. Keep these in sync with:

- `src/cloudbooter/free_tier.py`
- `setup_gcp_terraform.sh` / `setup_gcp_terraform.ps1`
- Terraform `check` blocks from the renderer

Numbers below match the Python constants as of July 2026. Always re-check Google's docs when something looks off.

## Compute Engine (`e2-micro`)

| Resource | Free limit | Notes |
|---|---|---|
| Machine type | `e2-micro` only | Other types bill |
| Combined compute hours | 744 / month | One instance 24/7 |
| Regions | `us-central1`, `us-west1`, `us-east1` | Only these three |
| Standard persistent disk | 30 GB total | `pd-standard` |
| Compute egress | 1 GB / month | Most destinations; China / Australia excluded |

## Cloud Storage

| Resource | Free limit | Notes |
|---|---|---|
| Storage | 5 GB | US regions only |
| Regions | `us-east1`, `us-west1`, `us-central1` | |
| Class A ops | 5,000 / month | |
| Class B ops | 50,000 / month | |
| Storage egress | 100 GB / month | NA destinations; China / Australia excluded |

## Other free allotments tracked in code

| Product | Free allotment |
|---|---|
| Secret Manager | 6 active versions, 10,000 access ops / month |
| Cloud Build | 2,500 build-minutes / month |
| Artifact Registry | 0.5 GB |
| Cloud Logging | 50 GiB ingestion / project / month |

Python also defines constants for Firestore, BigQuery, Cloud Run, and Cloud Functions. Those are not part of the Iteration 1 Terraform baseline — they are there so validators can grow without inventing numbers later.

## Cost traps

| Resource | Issue |
|---|---|
| External static IP reserved but unattached | Bills while idle |
| Cloud NAT | Per gateway-hour |
| Cloud DNS managed zone | Monthly per zone |
| Load balancer forwarding rules | Per rule-hour |
| Filestore / Cloud SQL / Spanner | No free tier for the usual cases |

CloudBooter warns or blocks these unless `GCP_ALLOW_PAID_RESOURCES=true`.

## Idle instances

Google may stop or reclaim underused Always Free VMs under published idle policies. Treat that as a provider rule, not something CloudBooter can fully paper over. Prefer real periodic work over synthetic CPU burners.

## Sync checklist

When Google changes a limit:

- [ ] `src/cloudbooter/free_tier.py`
- [ ] `setup_gcp_terraform.sh` `FREE_*` constants
- [ ] `setup_gcp_terraform.ps1` `$FREE_*` variables
- [ ] Terraform `check` blocks in the renderer
- [ ] This file

## Sources

- https://cloud.google.com/free/docs/free-cloud-features
- https://cloud.google.com/free/docs/gcp-free-tier
