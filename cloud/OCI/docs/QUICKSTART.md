# Oracle Cloud Always Free Tier — Quick Start

Hands-on walkthrough for creating Oracle Cloud instances plus limits and optimization tips.

> **Always Free A1 resources reduced (June 2026)**
> Oracle updated the Always Free allowance for `VM.Standard.A1.Flex` to **2 OCPUs and 12 GB memory** (previously 4 / 24). Cost Estimator / Cost Analysis forecasts may lag. Verify at [Oracle Always Free Resources](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm). See [FREE_TIER_LIMITS.md](FREE_TIER_LIMITS.md) for PAYG billing safety and resize guidance.
>
> **Billing safety (especially PAYG):** Free tier covers **200 GB total block storage** and your A1 OCPU/memory pool. Extra instances or volumes may incur charges on PAYG accounts.

---

## Overview

Oracle Cloud Infrastructure (OCI) **Always Free** resources are available **indefinitely** in your **home region** when you stay within limits. They are separate from the 30-day $300 trial.

For authoritative limits and automated provisioning, see [FREE_TIER_LIMITS.md](FREE_TIER_LIMITS.md) and [`setup_oci_terraform.sh`](../setup_oci_terraform.sh).

---

## Free Tier Resource Limits (At a Glance)

### Compute

- **AMD (x86):** up to **2** × `VM.Standard.E2.1.Micro` (1/8 OCPU, 1 GB RAM each)
- **Arm (A1 Flex):** **2 OCPUs + 12 GB RAM** total — typically **1 instance at 2/12** (recommended) or 2 instances at 1/6 each

### Storage

- **200 GB** block + boot combined
- **5** volume backups
- **20 GB** object/archive (post-trial)

### Networking

- 1 Flexible LB (10 Mbps), 1 NLB, 2 VCNs, **10 TB** egress/month

Full tables: [FREE_TIER_LIMITS.md](FREE_TIER_LIMITS.md)

---

## Step-by-Step: Creating an Always Free VM

### 1. Create Your Account

https://signup.cloud.oracle.com/ — valid credit/debit card required (no virtual/prepaid).

### 2. Navigate to Compute → Instances → Create instance

### 3. Image and Shape

- **Image:** Canonical **Ubuntu 24.04**
- **Shape:** `VM.Standard.A1.Flex` — **2 OCPUs**, **12 GB** memory

![Shape selection reference](https://user-images.githubusercontent.com/7338312/144945509-1d6f269e-47c9-4749-9281-b93c947637a2.png)

### 4. Networking

Create new VCN and public subnet (defaults are fine for a single VM).

### 5. SSH Keys

Generate ed25519 keys (recommended):

```bash
ssh-keygen -t ed25519 -C "your_email@example.com"
```

Upload `id_ed25519.pub`.

### 6. Boot Volume

Enable **Specify a custom boot volume size and performance**:

- Size: **200 GB**
- Performance: **120 VPU**

### 7. Deploy and Connect

```bash
ssh -i ~/.ssh/id_ed25519 ubuntu@<public-ip>
```

Open additional ports via the subnet security list (Networking tab → Subnet → Security rules).

---

## Automated Bootstrap (Recommended)

```bash
cd cloud/OCI
./setup_oci_terraform.sh
```

Choose **option 4 — Recommended (billing-safe)** for 1× A1 (2/12), 200 GB boot @ 120 VPU.

Non-interactive:

```bash
NON_INTERACTIVE=true AUTO_DEPLOY=true ./setup_oci_terraform.sh
```

---

## Maximizing Value

- **Default (billing-safe):** one A1 at full pool (2/12) with 200 GB boot — matches [viren070's guide](https://guides.viren070.me/selfhosting/oracle)
- **Advanced:** script option 5 (Maximum Free Tier) uses all AMD + A1 slots — **PAYG billing risk**; read warnings in [FREE_TIER_LIMITS.md](FREE_TIER_LIMITS.md)
- Keep instances active to avoid idle reclamation (7-day window, <20% utilization)
- PAYG upgrade improves capacity while staying $0 within Always Free limits — set a **$1 budget alert**

---

## Summary

Oracle Always Free is excellent for self-hosting and homelabs. The current Arm allowance is **2 OCPU / 12 GB** with **200 GB** storage — stay within limits for indefinite $0 usage.
