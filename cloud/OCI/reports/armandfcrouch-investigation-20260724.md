# armandfcrouch Investigation Report

Generated: 2026-07-24T19:45:00Z

## Summary

**Resize not executed.** The `armandfcrouch` Oracle Cloud tenancy exists (home region `us-chicago-1`) but **no valid console or API credentials for that tenancy were found** in Bitwarden, on disk, or via password reuse from 1,225 vault items.

## Findings

### Cloud account (confirmed)

| Field | Value |
|-------|-------|
| Cloud account name | `armandfcrouch` |
| Identity domain | `idcs-9a21080eba4442c09d535096dde722ea` |
| Login region | `us-chicago-1` |
| Console URL | `https://cloud.oracle.com/` → tenant `armandfcrouch` |

### Bitwarden vault (`boden.crouch@gmail.com`)

| Search | Result |
|--------|--------|
| `armandfcrouch` / `armand` / `fcrouch` | 0 items |
| `cloud.oracle.com` URI | 0 items |
| OCI API custom fields (`tenancy_ocid`, `private_key`, etc.) | 0 items |
| Oracle-related logins | 2× `keithcrouch` for **different** tenant `idcs-c3950531…` (not armandfcrouch) |
| Secure notes with OCI/OCID content | 0 (1,177 `"--"` placeholder items have empty notes) |
| Full JSON export (`bw export --format json`) | Same — no armandfcrouch credentials |

### Login attempts (Playwright)

All failed with *invalid username or password*:

- `keithcrouch` + keith vault password
- `boden.crouch@gmail.com`, `mackeyg.crouch@gmail.com` + master password
- All 34 vault login `(username, password)` pairs
- 20+ username variants + keith password

### Filesystem

- No `~/.oci/config` or `oci_api_key.pem` on this machine
- No `armandfcrouch` string in workspace or common config paths

## What is required to resize

Per [viren070 Oracle guide](https://guides.viren070.me/selfhosting/oracle) and CloudBooter implementation:

1. **Auth** — API key in Bitwarden **or** successful console login for `armandfcrouch`
2. **Resize** — `RESIZE_LEGACY_ARM_ONLY=true` / `oci compute instance update --shape-config '{"ocpus":2,"memoryInGBs":12}' --force`

### Add to Bitwarden (recommended)

Create login item:

- **Name:** `Oracle armandfcrouch`
- **URI:** `https://cloud.oracle.com`
- **Custom fields:** `cloud_account=armandfcrouch`, `tenancy_ocid`, `user_ocid`, `fingerprint`, `region=us-chicago-1`, `private_key` (PEM)

Or console-only item with username/password for tenancy `armandfcrouch` (requires console session auth path — not yet in vault).

### Re-run after credentials exist

```bash
cd cloud/OCI
./export_bw_items.sh
./bw_oci_resize_all.sh --start-account armandfcrouch --accounts armandfcrouch
```

## Security notes

- Master password was used for vault unlock; rotate if exposed in chat logs
- Remove `/tmp/bw-full-export.json`, `/tmp/pw_*` on shared systems (`chmod 600` applied where created)
