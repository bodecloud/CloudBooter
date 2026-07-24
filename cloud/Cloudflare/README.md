# CloudBooter Cloudflare

> Free-plan Workers / KV / R2 / D1 provisioner.
> Generates validated Terraform and optionally applies it — no VPC/VM/SSH (Cloudflare is edge/serverless).

---

## Quick Start

```bash
export CLOUDFLARE_API_TOKEN="..."
export CLOUDFLARE_ACCOUNT_ID="..."
./setup_cloudflare_terraform.sh
```

Windows: `setup_cloudflare_terraform.ps1`.

See [docs/QUICKSTART.md](docs/QUICKSTART.md) and [USAGE.md](USAGE.md).

---

## What Gets Created (Iteration 1 baseline)

| Resource | Terraform type | Free? |
|---|---|---|
| Worker (+ workers.dev) | `cloudflare_workers_script` + `cloudflare_workers_script_subdomain` | ✅ |
| KV namespace | `cloudflare_workers_kv_namespace` | ✅ |
| R2 bucket (Standard) | `cloudflare_r2_bucket` | ✅ |
| D1 database | `cloudflare_d1_database` | ✅ |

Optional Phase 2: Pages, Queues, Durable Objects (SQLite), DNS zone, Workers AI.

---

## Free-plan Guardrails

Three layers:

1. **Bash/PowerShell constants** — preflight
2. **Python `CloudflareFreeTierLimits`** — CLI + tests
3. **Terraform `check` blocks** — plan/apply

Override only with `CLOUDFLARE_ALLOW_PAID_RESOURCES=true`.

See [docs/FREE_TIER_LIMITS.md](docs/FREE_TIER_LIMITS.md).

---

## Directory Structure

```
cloud/Cloudflare/
├── setup_cloudflare_terraform.sh
├── setup_cloudflare_terraform.ps1
├── requirements.txt / pyproject.toml / pytest.ini
├── main.py / run_tests.py
├── src/cloudbooter/
│   ├── free_tier.py / renderers.py / auth.py
│   ├── inventory.py / installer.py / cli.py
├── tests/
└── docs/
```

---

## Non-Interactive (CI/CD)

```bash
CLOUDFLARE_API_TOKEN=... \
CLOUDFLARE_ACCOUNT_ID=... \
NON_INTERACTIVE=true \
AUTO_DEPLOY=false \
./setup_cloudflare_terraform.sh
```

---

## Running Tests

```bash
cd cloud/Cloudflare
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
python -m pytest tests/ -q
```

---

## Docs

- [USAGE.md](USAGE.md) — env vars and CLI
- [docs/OVERVIEW.md](docs/OVERVIEW.md) — architecture
- [docs/QUICKSTART.md](docs/QUICKSTART.md) — first run
- [docs/FREE_TIER_LIMITS.md](docs/FREE_TIER_LIMITS.md) — verified limits (2026-07-24)
