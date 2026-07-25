# Oracle Cloud Always Free limits

Reference for Always Free caps, PAYG safety, and how CloudBooter stays inside them. Verified against Oracle docs and [viren070's billing-safe guide](https://guides.viren070.me/selfhosting/oracle) as of **24 July 2026**.

> **June 2026 A1 reduction.** Always Free `VM.Standard.A1.Flex` is now **2 OCPUs and 12 GB memory** (was 4 / 24). Cost Estimator / Cost Analysis can still look wrong for a while. Confirm at [Oracle Always Free Resources](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm). If you still have a 4/24 instance, resize it — see below — before you rely on PAYG.

> **PAYG warning.** Pure Always Free accounts are not charged for in-tier resources. **Pay-as-you-go accounts are charged for anything above Always Free caps.** CloudBooter's default is one A1 (2/12) with a 200 GB boot volume and no extra instances.

## Core limits

| Category | Resource | Quota | Notes |
|---|---|---|---|
| Compute (AMD) | `VM.Standard.E2.1.Micro` | 2 instances | 1/8 OCPU, 1 GB RAM each; single AD in multi-AD regions |
| Compute (Arm) | `VM.Standard.A1.Flex` | **2 OCPU + 12 GB total** | 1×2/12 or 2×1/6; min boot ~47 GB |
| Block storage | Boot + block | 200 GB + 5 backups | Home region only |
| Object storage | Standard + IA + Archive | 20 GB combined (post-trial) | Over 20 GB at trial end deletes objects |
| Networking | LB / NLB / VCN / egress | 1 Flex LB (10 Mbps), 1 NLB, 2 VCNs, 10 TB egress/month | Port 25 blocked by default |

Optional Always Free databases (not created by the bootstrap script): Autonomous DB (2), MySQL HeatWave (1), NoSQL tables within published caps.

### Idle reclamation (official)

Oracle may reclaim idle Always Free compute if, over 7 days, CPU / network / memory (A1) utilization stay under about 20% at the 95th percentile. Keep real workloads on the instance. Do not run synthetic CPU burners just to dodge reclamation.

## CloudBooter profiles

| Profile | Menu | Layout | Best for |
|---|---|---|---|
| Recommended (billing-safe) | Option 4 (default) | 1× A1 (2/12), 200 GB boot @ 120 VPU | First deploy, PAYG accounts |
| Maximum Free Tier | Option 5 | All available AMD + A1 | Advanced homelab only — **PAYG risk** |

`NON_INTERACTIVE=true` always picks the billing-safe profile.

## PAYG upgrade and budgets

Upgrading to PAYG often improves A1 capacity. Always Free in-tier resources stay $0 if you stay inside the caps. Oracle places a temporary authorization hold on the card when you upgrade.

Recommended: create a **$1** budget with a low forecast threshold and an email alert the day you upgrade. Check **Cost Analysis** with forecast enabled and confirm it stays near $0 for Always Free-only usage.

You cannot downgrade a tenancy from PAYG back to Always Free-only.

Script behavior when limits are enforced (`ENFORCE_LIMITS=auto` on PAYG, or `true` always):

- Blocks Maximum Free Tier and over-cap custom plans
- Allows apply only when the **proposed** config is billing-safe
- Existing leftover resources elsewhere in the tenancy may still show on Cost Analysis until you remove or resize them

| `ENFORCE_LIMITS` | Behavior |
|---|---|
| `auto` (default) | Enforce on PAYG tenancies |
| `true` | Always enforce |
| `false` | Never enforce (power users) |

## Resizing a legacy 4/24 instance

Downsize to **2 OCPU / 12 GB**. The instance reboots; plan on 5–10 minutes.

Automated:

```bash
cd cloud/OCI
RESIZE_LEGACY_ARM_ONLY=true ./setup_oci_terraform.sh
```

```powershell
cd cloud/OCI
$env:RESIZE_LEGACY_ARM_ONLY = 'true'
.\setup_oci_terraform.ps1
```

| Variable | Behavior |
|---|---|
| `AUTO_RESIZE_LEGACY_ARM=auto` | Resize when `NON_INTERACTIVE=true` |
| `AUTO_RESIZE_LEGACY_ARM=true` | Always resize without prompting |
| `AUTO_RESIZE_LEGACY_ARM=false` | Never auto; use the interactive resize menu |
| `RESIZE_LEGACY_ARM_ONLY=true` | Auth, inventory, resize, exit |

Manual: **Compute** → instance → **Edit** → set A1 to 2 OCPU / 12 GB → save.

## Ingress defaults

Default security list allows SSH (port 22). Add ports with `EXTRA_INGRESS_PORTS=443,80`.

`OPEN_ALL_PORTS=true` opens wide public ingress. That is a last resort for debugging, not a recommended restore path.

## Sync checklist

When Always Free numbers change, update all of these in one PR:

- [ ] `setup_oci_terraform.sh` — `FREE_TIER_*` constants
- [ ] `setup_oci_terraform.ps1` — `$FREE_TIER_*` variables
- [ ] `src/cloudbooter/free_tier.py`
- [ ] Terraform `check` blocks in the generator
- [ ] This file, plus QUICKSTART / OVERVIEW / provider README

## References

- [Oracle Always Free Resources](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)
- [Oracle Cloud Free Tier](https://www.oracle.com/cloud/free/)
- [viren070 Oracle VPS guide](https://guides.viren070.me/selfhosting/oracle)
- [OCI Free Tier FAQ](https://www.oracle.com/cloud/free/faq/)
