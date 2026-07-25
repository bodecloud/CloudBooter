# Cloudflare usage

Entrypoints, environment variables, and auth notes for the Cloudflare scaffold.

## Entrypoints

| Entrypoint | Platform |
|---|---|
| `./setup_cloudflare_terraform.sh` | Linux / macOS / WSL |
| `.\setup_cloudflare_terraform.ps1` | Windows |
| `cloudbooter-cloudflare` / `python -m cloudbooter` | All (Click CLI after `pip install -e .`) |

## CLI

```bash
cd cloud/Cloudflare
pip install -e .

python -m cloudbooter deploy \
  --account-id "$CLOUDFLARE_ACCOUNT_ID" \
  --api-token "$CLOUDFLARE_API_TOKEN" \
  --output-dir ./tf

python -m cloudbooter validate
python -m cloudbooter inventory --account-id "$CLOUDFLARE_ACCOUNT_ID"
python -m cloudbooter install-deps
```

Prefer passing the token on the CLI or via `CLOUDFLARE_API_TOKEN` / `CLOUDFLARE_API_TOKEN_FILE`. If a command writes `terraform.tfvars`, do not commit that file.

## Environment variables

### Cloudflare-specific

| Variable | Purpose | Default |
|---|---|---|
| `CLOUDFLARE_API_TOKEN` | API token | required |
| `CLOUDFLARE_API_TOKEN_FILE` | Path to a token file | (none) |
| `CLOUDFLARE_ACCOUNT_ID` | Account ID | required |
| `CLOUDFLARE_ZONE_ID` | Optional zone ID | (none) |
| `CLOUDFLARE_ZONE_NAME` | Optional zone name | (none) |
| `CLOUDFLARE_WORKER_NAME` | Worker script name | `cloudbooter-worker` |
| `CLOUDFLARE_R2_BUCKET` | R2 bucket name | `cloudbooter-r2` |
| `CLOUDFLARE_D1_NAME` | D1 database name | `cloudbooter-db` |
| `CLOUDFLARE_KV_TITLE` | KV namespace title | `cloudbooter-kv` |
| `CLOUDFLARE_WORKERS_CPU_MS` | CPU ms (Free max 10) | `10` |
| `CLOUDFLARE_R2_STORAGE_CLASS` | R2 class (Free-safe: Standard) | `Standard` |
| `CLOUDFLARE_ALLOW_PAID_RESOURCES` | Bypass free-plan guards | `false` |
| `CF_MODE` | `wrangler` / `npx` / `api` | auto |

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

1. Create a token at https://dash.cloudflare.com/profile/api-tokens with edit access for Workers, KV, R2, and D1 (plus Zone DNS if you manage zones).
2. Export `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID`.
3. Optional interactive path: `wrangler login` when `CF_MODE=wrangler`.

Terraform uses provider `cloudflare/cloudflare` `~> 5` with `api_token`. Wrangler is not required for apply.

## Generated files

- `provider.tf` — Cloudflare provider
- `variables.tf` — inputs + free-plan `check` blocks
- `main.tf` — Worker, KV, R2, D1, workers.dev
- `worker.mjs` — minimal ESM Worker source

## Safety

Review `terraform plan` before apply. Free-plan caps are daily or monthly quotas — hitting them fails requests (for example Workers Error 1027). You are not silently upgraded to Paid unless you turn on paid features yourself.

## More docs

- [README.md](README.md)
- [docs/QUICKSTART.md](docs/QUICKSTART.md)
- [docs/OVERVIEW.md](docs/OVERVIEW.md)
- [docs/FREE_TIER_LIMITS.md](docs/FREE_TIER_LIMITS.md)
