# Security policy

## Reporting a vulnerability

Do **not** open a public issue with credentials, tenancy OCIDs, API tokens, Bitwarden exports, Terraform state, private keys, or full unredacted logs.

Prefer [GitHub Security Advisories](https://github.com/bodecloud/CloudBooter/security/advisories/new) for this repository. If that is unavailable, open a private contact with the maintainer through GitHub and say you need to report a security issue — wait for a channel before pasting secrets.

We will acknowledge reports as soon as we can. This is a hobby-scale project; there is no SLA.

## What counts as in scope

Issues in CloudBooter scripts or CLIs that:

- Leak credentials into generated files, logs, or the git tree
- Bypass free-tier / free-plan checks in a way that can create unexpected billable resources
- Write secrets into committed paths by default

## Out of scope

- Cloud provider outages or capacity problems
- Account compromise from misconfigured user credentials
- Free-tier policy changes by Oracle, Google, or Cloudflare
- Asking maintainers to create API keys inside your tenancy

## Handling credentials in this project

- Put secrets in environment variables, a password manager, or a credentials file you keep outside git.
- Never commit Bitwarden exports, `.bw-items.json`, PEM material, or `terraform.tfvars` that contain tokens.
- Prefer passing tokens via env / `-var` over writing them into files that might be committed.
- Rotate anything that was pasted into a chat, issue, or PR by mistake.

Generated Terraform, SSH keys, and state files are gitignored on purpose. Keep them that way.
