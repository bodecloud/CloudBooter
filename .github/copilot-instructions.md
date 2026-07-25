# CloudBooter — agent instructions

CloudBooter is a local multi-cloud bootstrap toolkit. Each provider lives under `cloud/<PROVIDER>/` with its own setup scripts, Python package, tests, and docs. There is no root installable package.

## Providers

| Path | Status | Default baseline |
|---|---|---|
| `cloud/OCI/` | Supported | Always Free A1 2 OCPU / 12 GB, 200 GB boot |
| `cloud/GCP/` | In progress | `e2-micro` in us-central1 / us-west1 / us-east1 |
| `cloud/Cloudflare/` | In progress | Worker + KV + R2 + D1 on the Free plan |

Shared workflow: authenticate → inventory → validate free-tier caps → generate Terraform → optionally apply.

## Shared env vars

`NON_INTERACTIVE`, `AUTO_USE_EXISTING`, `AUTO_DEPLOY`, `SKIP_CONFIG`, `DEBUG`, `FORCE_REAUTH`, `RETRY_MAX_ATTEMPTS`, `RETRY_BASE_DELAY`.

Provider-specific vars are documented in each `USAGE.md`.

## Free-tier sync rule

When limits change, update **all** of these in one change:

1. Bash / PowerShell constants in the setup scripts
2. `src/cloudbooter/free_tier.py`
3. Terraform `check` blocks from the renderer
4. `docs/FREE_TIER_LIMITS.md`

Canonical docs:

- OCI: `cloud/OCI/docs/FREE_TIER_LIMITS.md`
- GCP: `cloud/GCP/docs/FREE_TIER_LIMITS.md`
- Cloudflare: `cloud/Cloudflare/docs/FREE_TIER_LIMITS.md`

## Tests

```bash
cd cloud/OCI && python -m pytest tests/
cd cloud/GCP && python -m pytest tests/
cd cloud/Cloudflare && python -m pytest tests/
```

CI does not yet run these suites. It only blocks committed `backend.tf` and shellchecks one helper script.

## Do not commit

- Secrets, Bitwarden exports, PEM keys, API tokens
- `ssh_keys/`, `*.tfstate`, `backend.tf`, credential-bearing `terraform.tfvars`
- Generated provider `.tf` files that belong in a working directory, not git

See `SECURITY.md` and `.gitignore`.

## Docs conventions

- Prefer plain language in user-facing Markdown.
- Planning docs need a Mermaid `flowchart TD` near the top (`CONVENTIONS.md`).
- `.github/instructions/` contains vendored Taskmaster / editor material. It is not product documentation for this repo.
- Historical plans live under `docs/plans/` and `.github/prompts/plan-*.prompt.md` — do not treat them as current contributor guides.

## Editing guidance

- Work inside one provider tree unless the task is truly cross-cutting.
- Match existing code style; keep diffs small.
- Update docs when user-visible behavior changes.
- Never hardcode credentials. Read them from the environment, a credentials file outside git, or the operator vault helpers.
