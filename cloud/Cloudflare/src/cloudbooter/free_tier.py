"""Cloudflare Workers Free / Free-plan hard limits — canonical source for all layers.

Keep in sync with:
  - shell: setup_cloudflare_terraform.sh constants block
  - Terraform: variables.tf check blocks
  - docs: FREE_TIER_LIMITS.md

Verified 2026-07-24 via Cloudflare docs:
  https://developers.cloudflare.com/workers/platform/limits/
  https://developers.cloudflare.com/workers/platform/pricing/
  https://developers.cloudflare.com/durable-objects/platform/pricing/
  https://developers.cloudflare.com/r2/pricing/
  https://developers.cloudflare.com/pages/platform/limits/
  https://developers.cloudflare.com/workers-ai/platform/pricing/
  https://developers.cloudflare.com/changelog/post/2026-02-04-queues-free-plan/
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CloudflareFreeTierLimits:
    # ── Workers ───────────────────────────────────────────────────────────────
    free_workers_requests_per_day: int = 100_000
    free_workers_cpu_ms: int = 10
    free_workers_memory_mb: int = 128
    free_workers_subrequests: int = 50
    free_workers_size_mb: int = 3
    free_workers_count: int = 100
    free_cron_triggers: int = 5

    # ── KV ────────────────────────────────────────────────────────────────────
    free_kv_reads_per_day: int = 100_000
    free_kv_writes_per_day: int = 1_000
    free_kv_deletes_per_day: int = 1_000
    free_kv_lists_per_day: int = 1_000
    free_kv_storage_gb: int = 1

    # ── R2 ────────────────────────────────────────────────────────────────────
    free_r2_storage_gb: int = 10
    free_r2_class_a_ops_per_month: int = 1_000_000
    free_r2_class_b_ops_per_month: int = 10_000_000
    free_r2_storage_class: str = "Standard"

    # ── D1 ────────────────────────────────────────────────────────────────────
    free_d1_rows_read_per_day: int = 5_000_000
    free_d1_rows_written_per_day: int = 100_000
    free_d1_storage_gb: int = 5

    # ── Durable Objects (SQLite only on Free) ─────────────────────────────────
    free_do_requests_per_day: int = 100_000
    free_do_duration_gb_s_per_day: int = 13_000
    free_do_sql_storage_gb: int = 5
    free_do_backend: str = "sqlite"

    # ── Queues / Pages / AI ───────────────────────────────────────────────────
    free_queues_ops_per_day: int = 10_000
    free_pages_builds_per_month: int = 500
    free_pages_files_per_site: int = 20_000
    free_pages_projects: int = 100
    free_workers_ai_neurons_per_day: int = 10_000

    # ── Budget guards (non-free — block/warn by default) ─────────────────────
    cost_trap_workers_paid_features: bool = True
    cost_trap_r2_infrequent_access: bool = True
    cost_trap_load_balancer: bool = True
    cost_trap_kv_backed_do: bool = True


LIMITS = CloudflareFreeTierLimits()


def validate_proposed_config(
    *,
    workers_cpu_ms: int = 10,
    r2_storage_class: str = "Standard",
    do_backend: str | None = None,
    enable_load_balancer: bool = False,
    worker_count: int = 1,
    allow_paid_resources: bool = False,
) -> list[str]:
    """Validate a proposed Cloudflare config against Free-plan limits.

    Returns a list of error/warning strings. Empty list = valid.
    Warnings are prefixed with 'WARN:'; hard failures with 'ERROR:'.
    """
    errors: list[str] = []
    limits = LIMITS

    if allow_paid_resources:
        return errors

    if workers_cpu_ms > limits.free_workers_cpu_ms:
        errors.append(
            f"ERROR: Workers CPU limit {workers_cpu_ms} ms exceeds Free plan "
            f"({limits.free_workers_cpu_ms} ms). "
            f"Set CLOUDFLARE_ALLOW_PAID_RESOURCES=true to override."
        )

    if r2_storage_class.lower() != limits.free_r2_storage_class.lower():
        errors.append(
            f"ERROR: R2 storage class '{r2_storage_class}' is not free-safe. "
            f"Use '{limits.free_r2_storage_class}' (Infrequent Access has retrieval fees). "
            f"Set CLOUDFLARE_ALLOW_PAID_RESOURCES=true to override."
        )

    if do_backend is not None and do_backend.lower() != limits.free_do_backend:
        errors.append(
            f"ERROR: Durable Objects backend '{do_backend}' requires Workers Paid. "
            f"Free plan allows only '{limits.free_do_backend}'. "
            f"Set CLOUDFLARE_ALLOW_PAID_RESOURCES=true to override."
        )

    if enable_load_balancer:
        errors.append(
            "ERROR: Cloudflare Load Balancers are billable and blocked by default. "
            "Set CLOUDFLARE_ALLOW_PAID_RESOURCES=true to override."
        )

    if worker_count > limits.free_workers_count:
        errors.append(
            f"ERROR: Worker count {worker_count} exceeds Free plan cap "
            f"of {limits.free_workers_count}."
        )

    if workers_cpu_ms == limits.free_workers_cpu_ms and worker_count > 50:
        errors.append(
            f"WARN: Creating {worker_count} Workers approaches the Free plan "
            f"cap of {limits.free_workers_count}."
        )

    return errors
