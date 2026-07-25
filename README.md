# CloudBooter

CloudBooter bootstraps cloud accounts from the terminal. It looks at what you already have, stays inside free-tier limits where it can, writes plain Terraform you can read, and only applies when you say so.

Oracle Cloud (OCI) is the mature path today. GCP and Cloudflare are usable scaffolds. AWS and Azure are planned.

## Support status

| Provider | Status | Notes |
|---|---|---|
| OCI | Supported | Bash + PowerShell setup scripts, Python CLI, Always Free guardrails, optional Bitwarden multi-account resize |
| GCP | In progress | `e2-micro` baseline under `cloud/GCP/` |
| Cloudflare | In progress | Workers + KV + R2 + D1 free-plan baseline under `cloud/Cloudflare/` |
| AWS | Planned | VPC + EC2 baseline |
| Azure | Planned | Resource group + VNet + VM baseline |

## How it works

Same shape on every provider:

1. Authenticate with that cloud's usual local method.
2. Inventory existing resources.
3. Plan a small default configuration (prompts, or env vars for automation).
4. Validate against free-tier / free-plan caps.
5. Generate Terraform into a directory you can inspect.
6. Optionally run `terraform init`, `plan`, and `apply`.

## Quick start (OCI)

Oracle cut Always Free A1 to **2 OCPU / 12 GB** in June 2026. The default profile is one A1 instance with a 200 GB boot volume. Details: [cloud/OCI/docs/FREE_TIER_LIMITS.md](cloud/OCI/docs/FREE_TIER_LIMITS.md).

```bash
cd cloud/OCI
./setup_oci_terraform.sh
```

Windows:

```powershell
cd cloud\OCI
.\setup_oci_terraform.ps1
```

Generate without applying:

```bash
NON_INTERACTIVE=true AUTO_DEPLOY=false ./setup_oci_terraform.sh
```

Then open the generated `.tf` files, run `terraform plan`, and apply only if the plan looks right.

Provider docs:

- [OCI](cloud/OCI/README.md) · [USAGE](cloud/OCI/USAGE.md)
- [GCP](cloud/GCP/README.md)
- [Cloudflare](cloud/Cloudflare/README.md)

## What gets generated

Filenames vary by provider. OCI typically writes:

- `provider.tf`, `variables.tf`, `data_sources.tf`, `main.tf`
- optional `block_volumes.tf`
- `cloud-init.yaml`
- SSH keys under `./ssh_keys/` (gitignored)

Treat the folder as disposable while you learn. If you keep a stack, move it to its own repo and use a remote state backend.

## Cost and cleanup

Cloud accounts bill. Free tiers change. Habits that keep you out of trouble:

1. Read `terraform plan` before every apply.
2. Set a budget alert on day one.
3. Prefer the billing-safe defaults.
4. Run `terraform destroy` when you are done experimenting.
5. Know where your state file lives.

## Repository layout

```text
.
├─ cloud/
│  ├─ OCI/           # reference implementation
│  ├─ GCP/           # in progress
│  └─ Cloudflare/    # in progress
├─ helper_scripts/   # small ops helpers (not the main product)
├─ docs/plans/       # design notes
├─ CONTRIBUTING.md
├─ SECURITY.md
├─ SUPPORT.md
└─ LICENSE
```

Each provider directory has its own README, usage notes, and docs.

## Developing

Providers own their own dependencies and tests.

```bash
cd cloud/OCI && python -m pytest tests/
cd cloud/GCP && python -m pytest tests/
cd cloud/Cloudflare && python -m pytest tests/
```

CI currently checks that `backend.tf` is not committed and shellchecks one helper script. It does not yet run the full pytest suites — run those locally before you open a PR.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Short version: work in one `cloud/<PROVIDER>/` tree, keep free-tier constants in sync across shell/Python/docs, and never commit secrets or Terraform state.

## License

MIT. See [LICENSE](LICENSE).
