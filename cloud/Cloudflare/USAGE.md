# CloudBooter Cloudflare — Usage

## Entrypoints

| Entrypoint | Platform |
|---|---|
| `./setup_cloudflare_terraform.sh` | Linux / macOS / WSL |
| `.\setup_cloudflare_terraform.ps1` | Windows |
| `python -m cloudbooter` / `python main.py` | All (Click CLI) |

## CLI commands

```bash
export PYTHONPATH=src
python -m cloudbooter deploy --account-id ID --api-token TOKEN --output-dir ./tf
python -m cloudbooter validate
python -m cloudbooter inventory --account-id ID
python -m cloudbooter install-deps
```

## Environment variables

### Cloudflare-specific

| Variable | Purpose | Default |
|---|---|---|
| `CLOUDFLARE_API_TOKEN` | API token (Terraform + inventory) | — |
| `CLOUDFLARE_API_TOKEN_FILE` | Path to token file | — |
| `CLOUDFLARE_ACCOUNT_ID` | Account ID | — |
| `CLOUDFLARE_ZONE_ID` | Optional zone ID | — |
| `CLOUDFLARE_ZONE_NAME` | Optional zone name | — |
| `CLOUDFLARE_WORKER_NAME` | Worker script name | `cloudbooter-worker` |
| `CLOUDFLARE_R2_BUCKET` | R2 bucket name | `cloudbooter-r2` |
| `CLOUDFLARE_D1_NAME` | D1 database name | `cloudbooter-db` |
| `CLOUDFLARE_KV_TITLE` | KV namespace title | `cloudbooter-kv` |
| `CLOUDFLARE_WORKERS_CPU_MS` | CPU ms (Free max 10) | `10` |
| `CLOUDFLARE_R2_STORAGE_CLASS` | R2 class (Free-safe: Standard) | `Standard` |
| `CLOUDFLARE_ALLOW_PAID_RESOURCES` | Bypass free-tier guards | `false` |
| `CF_MODE` | `wrangler` / `npx` / `api` | auto |

### Shared (multi-provider)

| Variable | Purpose |
|---|---|
| `NON_INTERACTIVE` | No prompts |
| `AUTO_USE_EXISTING` | Prefer discovered resources |
| `AUTO_DEPLOY` | Run `terraform apply` after generate |
| `SKIP_CONFIG` | Skip config prompts |
| `DEBUG` | Trace shell (`set -x`) |
| `FORCE_REAUTH` | Force re-auth |
| `RETRY_MAX_ATTEMPTS` | Apply retries (default 8) |
| `RETRY_BASE_DELAY` | Backoff base seconds (default 15) |

## Auth notes

1. Create a token at https://dash.cloudflare.com/profile/api-tokens with Workers, R2, D1, KV (and Zone DNS if using zones).
2. Export `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID`.
3. Interactive alternative: `wrangler login` (when `CF_MODE=wrangler`).

Terraform provider: `cloudflare/cloudflare` `~> 5`, `api_token = var.cloudflare_api_token`.

## Generated files

- `provider.tf` — Cloudflare provider
- `variables.tf` — inputs + free-tier `check` blocks
- `main.tf` — Worker, KV, R2, D1, workers.dev
- `worker.mjs` — minimal ESM Worker source
- `terraform.tfvars` — token (when passed on CLI; do not commit)

## Safety

Always review `terraform plan`. Free-plan caps are daily/monthly quotas — exceeding them fails requests (e.g. Workers Error 1027), it does not silently upgrade you to Paid unless you enable Paid features.
