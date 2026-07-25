# Cloudflare Free-plan limits

Verified **24 July 2026** against Cloudflare docs. Canonical constants live in `src/cloudbooter/free_tier.py`, the setup scripts, and Terraform `check` blocks.

## Sources

- https://developers.cloudflare.com/workers/platform/limits/
- https://developers.cloudflare.com/workers/platform/pricing/
- https://developers.cloudflare.com/durable-objects/platform/pricing/
- https://developers.cloudflare.com/r2/pricing/
- https://developers.cloudflare.com/pages/platform/limits/
- https://developers.cloudflare.com/workers-ai/platform/pricing/
- https://developers.cloudflare.com/changelog/post/2026-02-04-queues-free-plan/
- https://developers.cloudflare.com/changelog/post/2025-04-07-durable-objects-free-tier/

## Workers Free

| Limit | Value |
|---|---|
| Requests | 100,000 / day |
| CPU time (HTTP / Cron) | 10 ms |
| Memory | 128 MB |
| Subrequests | 50 / request |
| Worker size | 3 MB |
| Workers per account | 100 |
| Cron Triggers | 5 |

## KV

| Limit | Value |
|---|---|
| Reads | 100,000 / day |
| Writes / Deletes / Lists | 1,000 / day each |
| Stored data | 1 GB |

## R2

| Limit | Value |
|---|---|
| Storage | 10 GB-month / month |
| Class A | 1,000,000 / month |
| Class B | 10,000,000 / month |
| Egress | Free |
| Free-safe class | **Standard** (avoid Infrequent Access retrieval fees) |

## D1

| Limit | Value |
|---|---|
| Rows read | 5,000,000 / day |
| Rows written | 100,000 / day |
| Storage | 5 GB total |

## Durable Objects (Free — SQLite only)

| Limit | Value |
|---|---|
| Requests | 100,000 / day |
| Duration | 13,000 GB-s / day |
| SQL rows read / written | 5M / 100k per day |
| SQL storage | 5 GB total |
| KV-backed DO | Not available on Free |

## Queues / Pages / Workers AI

| Product | Free allotment |
|---|---|
| Queues | 10,000 operations / day (24 h retention) |
| Pages | 500 builds / month, 1 concurrent, 20,000 files / site, 100 projects |
| Workers AI | 10,000 Neurons / day |

These are tracked for later modules. Iteration 1 does not generate them by default.

## Cost traps

| Item | Policy |
|---|---|
| Workers CPU > 10 ms / paid-only features | Block |
| R2 Infrequent Access | Block (retrieval fees) |
| KV-backed Durable Objects | Block |
| Load Balancers / Argo / Spectrum / Containers | Block |

Override: `CLOUDFLARE_ALLOW_PAID_RESOURCES=true`.

## Rough comparison with the other providers

| Capability | OCI Always Free | GCP Always Free | Cloudflare Free |
|---|---|---|---|
| Long-running VM | Yes (A1 / AMD Micro) | `e2-micro` 744 h/month | No — Workers |
| Object storage | 20 GB post-trial | 5 GB (US) | R2 10 GB (egress free) |
| SQL-ish | Autonomous DB | — | D1 5 GB |
| Key-value | OCI NoSQL / JSON options | Firestore | Workers KV |

Use each provider's own `FREE_TIER_LIMITS.md` as the source of truth for that cloud.
