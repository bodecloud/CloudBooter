# Contributing to CloudBooter

Thanks for helping. This repo is a multi-cloud toolkit: each cloud lives under `cloud/<PROVIDER>/` and owns its scripts, Python package, tests, and docs.

## Before you start

- Python 3.11+
- Terraform if you want to validate or apply generated plans
- The provider CLI you are working on is optional for many dry-run tests (OCI CLI, `gcloud`, or Wrangler)

Pick one provider directory and stay there. There is no root Python package.

## Setup and tests

```bash
cd cloud/OCI          # or GCP / Cloudflare
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
python -m pytest tests/
```

CI currently:

- Rejects committed `backend.tf` / `backend/*.tf`
- Shellchecks `helper_scripts/post-provision-bodecloud-infra.sh`

It does **not** run the full pytest suites yet. Run them locally before opening a PR.

## Adding or changing a provider

Aim for the same workflow as OCI:

1. Authenticate
2. Inventory existing resources
3. Plan a small default
4. Validate free-tier / free-plan caps
5. Generate Terraform
6. Optionally apply

When free-tier numbers change, update every layer in the same PR:

- setup script constants (Bash and PowerShell)
- `src/cloudbooter/free_tier.py`
- Terraform `check` blocks produced by the renderer
- `docs/FREE_TIER_LIMITS.md`

## Docs

- User-facing behavior changes need a doc update in the same PR.
- New design / planning docs need a Mermaid flowchart near the top. See [CONVENTIONS.md](CONVENTIONS.md).
- `.github/instructions/` holds vendored editor tooling notes (Taskmaster). Do not treat those files as project product docs.

## Secrets and generated files

Do not commit:

- API tokens, PEM keys, Bitwarden exports, vault session files
- `ssh_keys/`, `*.tfstate`, `backend.tf`
- Generated `*.tf` / `terraform.tfvars` that contain credentials

See [SECURITY.md](SECURITY.md).

## Pull requests

Please include:

- Which provider path you touched
- How you tested it (`pytest`, dry-run script, or both)
- Whether free-tier constants or docs needed a sync
- Confirmation that no secrets or Terraform state are in the diff

## Questions

See [SUPPORT.md](SUPPORT.md).
