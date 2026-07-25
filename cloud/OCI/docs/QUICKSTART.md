# OCI quick start

Get one Always Free-friendly VM running, either with CloudBooter or in the console.

Oracle cut Always Free A1 to **2 OCPU / 12 GB** in June 2026 (was 4 / 24). Cost Estimator forecasts can lag. Confirm current numbers at [Oracle Always Free Resources](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm). Full limits and PAYG notes: [FREE_TIER_LIMITS.md](FREE_TIER_LIMITS.md).

## Limits at a glance

- **AMD:** up to 2 × `VM.Standard.E2.1.Micro` (1/8 OCPU, 1 GB each)
- **Arm A1:** 2 OCPU + 12 GB total — usually one instance at 2/12
- **Block / boot storage:** 200 GB combined
- **Home region only** for Always Free compute

## Automated path (recommended)

```bash
cd cloud/OCI
./setup_oci_terraform.sh
```

Choose **option 4 — Recommended (billing-safe)** for 1× A1 (2/12) with a 200 GB boot volume at 120 VPU.

Non-interactive:

```bash
NON_INTERACTIVE=true AUTO_DEPLOY=false ./setup_oci_terraform.sh
```

Then:

```bash
terraform init
terraform plan
terraform apply   # only if the plan looks right
```

SSH with the key under `./ssh_keys/` (Ubuntu images use the `ubuntu` user).

## Console path

1. Sign up at https://signup.cloud.oracle.com/ with a real credit or debit card (virtual / prepaid cards are rejected). Pick your home region carefully — it cannot be changed.
2. Console → **Compute** → **Instances** → **Create instance**.
3. Image: Canonical **Ubuntu 24.04**. Shape: `VM.Standard.A1.Flex` at **2 OCPUs** and **12 GB** memory.
4. Create a new VCN and public subnet (defaults are fine for a single VM).
5. Paste an ed25519 public key:

   ```bash
   ssh-keygen -t ed25519 -C "you@example.com"
   ```

6. Custom boot volume: **200 GB**, performance **120 VPU**.
7. Create the instance, wait until it is Running, then:

   ```bash
   ssh -i ~/.ssh/id_ed25519 ubuntu@<public-ip>
   ```

8. Open extra ports only if you need them (subnet security list). Prefer specific ports over wide-open rules.

## After you have a VM

- Prefer the billing-safe single A1 layout on PAYG accounts.
- Set a **$1 budget alert** if you upgrade to PAYG for better capacity.
- Idle Always Free instances can be reclaimed after sustained low use — keep real work on the box, not synthetic load generators.
- Tear down with `terraform destroy` when you generated the stack with CloudBooter.
