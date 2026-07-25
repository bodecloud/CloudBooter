# Support

## Start with the docs

1. Root [README.md](README.md) for the overall workflow
2. Provider README and USAGE under `cloud/<PROVIDER>/`
3. `docs/QUICKSTART.md` and `docs/FREE_TIER_LIMITS.md` for that provider

## Bugs and feature requests

Use GitHub Issues on [bodecloud/CloudBooter](https://github.com/bodecloud/CloudBooter).

Please include:

- Provider (`OCI`, `GCP`, or `Cloudflare`)
- OS and shell (Bash, PowerShell, WSL)
- Interactive vs `NON_INTERACTIVE=true`
- Whether Terraform was only generated or also applied
- Redacted command output (strip tokens, keys, tenancy OCIDs, emails)

## What we do not provide

- Free cloud credits or account recovery
- Creating API keys inside your cloud console
- Guaranteed response times

CloudBooter is maintained as a spare-time project. Always review `terraform plan`, set a budget alert with your provider, and destroy resources when you are done experimenting.
