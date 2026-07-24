"""Tests for Cloudflare free-tier constants and validation logic."""
from __future__ import annotations

import pytest

from cloudbooter.free_tier import CloudflareFreeTierLimits, LIMITS, validate_proposed_config


class TestCloudflareFreeTierLimitsConstants:
    def test_workers_requests_100k(self):
        assert LIMITS.free_workers_requests_per_day == 100_000

    def test_workers_cpu_10ms(self):
        assert LIMITS.free_workers_cpu_ms == 10

    def test_workers_memory_128(self):
        assert LIMITS.free_workers_memory_mb == 128

    def test_workers_count_100(self):
        assert LIMITS.free_workers_count == 100

    def test_kv_reads_100k(self):
        assert LIMITS.free_kv_reads_per_day == 100_000

    def test_kv_writes_1k(self):
        assert LIMITS.free_kv_writes_per_day == 1_000

    def test_kv_storage_1gb(self):
        assert LIMITS.free_kv_storage_gb == 1

    def test_r2_storage_10gb(self):
        assert LIMITS.free_r2_storage_gb == 10

    def test_r2_class_a_1m(self):
        assert LIMITS.free_r2_class_a_ops_per_month == 1_000_000

    def test_r2_class_b_10m(self):
        assert LIMITS.free_r2_class_b_ops_per_month == 10_000_000

    def test_r2_storage_class_standard(self):
        assert LIMITS.free_r2_storage_class == "Standard"

    def test_d1_rows_read_5m(self):
        assert LIMITS.free_d1_rows_read_per_day == 5_000_000

    def test_d1_rows_written_100k(self):
        assert LIMITS.free_d1_rows_written_per_day == 100_000

    def test_d1_storage_5gb(self):
        assert LIMITS.free_d1_storage_gb == 5

    def test_do_requests_100k(self):
        assert LIMITS.free_do_requests_per_day == 100_000

    def test_do_duration_13k(self):
        assert LIMITS.free_do_duration_gb_s_per_day == 13_000

    def test_do_backend_sqlite(self):
        assert LIMITS.free_do_backend == "sqlite"

    def test_queues_10k(self):
        assert LIMITS.free_queues_ops_per_day == 10_000

    def test_pages_builds_500(self):
        assert LIMITS.free_pages_builds_per_month == 500

    def test_pages_files_20k(self):
        assert LIMITS.free_pages_files_per_site == 20_000

    def test_workers_ai_10k_neurons(self):
        assert LIMITS.free_workers_ai_neurons_per_day == 10_000

    def test_cost_traps_enabled(self):
        assert LIMITS.cost_trap_workers_paid_features is True
        assert LIMITS.cost_trap_r2_infrequent_access is True
        assert LIMITS.cost_trap_load_balancer is True
        assert LIMITS.cost_trap_kv_backed_do is True

    def test_dataclass_is_frozen(self):
        with pytest.raises((AttributeError, TypeError)):
            LIMITS.free_workers_cpu_ms = 50  # type: ignore[misc]

    def test_module_singleton_type(self):
        assert isinstance(LIMITS, CloudflareFreeTierLimits)

    def test_new_instance_equals_singleton(self):
        assert CloudflareFreeTierLimits() == LIMITS


class TestValidateProposedConfigValid:
    def test_canonical_free_config(self):
        assert validate_proposed_config() == []

    def test_explicit_standard_r2(self):
        assert validate_proposed_config(r2_storage_class="Standard") == []

    def test_sqlite_do(self):
        assert validate_proposed_config(do_backend="sqlite") == []

    def test_cpu_at_cap(self):
        assert validate_proposed_config(workers_cpu_ms=10) == []


class TestValidateProposedConfigCpu:
    def test_rejects_50ms(self):
        errors = validate_proposed_config(workers_cpu_ms=50)
        assert len(errors) == 1
        assert errors[0].startswith("ERROR:")
        assert "50" in errors[0]
        assert "10" in errors[0]

    def test_allow_paid_bypasses_cpu(self):
        assert validate_proposed_config(workers_cpu_ms=30000, allow_paid_resources=True) == []

    def test_cpu_error_mentions_override(self):
        errors = validate_proposed_config(workers_cpu_ms=50)
        assert "CLOUDFLARE_ALLOW_PAID_RESOURCES" in errors[0]


class TestValidateProposedConfigR2:
    def test_rejects_infrequent_access(self):
        errors = validate_proposed_config(r2_storage_class="InfrequentAccess")
        assert len(errors) == 1
        assert "ERROR:" in errors[0]
        assert "InfrequentAccess" in errors[0]

    def test_allow_paid_bypasses_r2(self):
        assert validate_proposed_config(
            r2_storage_class="InfrequentAccess", allow_paid_resources=True
        ) == []


class TestValidateProposedConfigDO:
    def test_rejects_kv_backend(self):
        errors = validate_proposed_config(do_backend="kv")
        assert len(errors) == 1
        assert "kv" in errors[0]
        assert "sqlite" in errors[0]

    def test_allow_paid_bypasses_do(self):
        assert validate_proposed_config(do_backend="kv", allow_paid_resources=True) == []


class TestValidateProposedConfigLoadBalancer:
    def test_rejects_lb(self):
        errors = validate_proposed_config(enable_load_balancer=True)
        assert any("Load Balancer" in e for e in errors)

    def test_allow_paid_bypasses_lb(self):
        assert validate_proposed_config(
            enable_load_balancer=True, allow_paid_resources=True
        ) == []


class TestValidateProposedConfigWorkerCount:
    def test_rejects_over_cap(self):
        errors = validate_proposed_config(worker_count=101)
        assert any("101" in e for e in errors)

    def test_warns_when_approaching_cap(self):
        errors = validate_proposed_config(worker_count=75)
        assert any(e.startswith("WARN:") for e in errors)

    def test_allow_paid_bypasses_count(self):
        assert validate_proposed_config(worker_count=500, allow_paid_resources=True) == []


class TestValidateProposedConfigMultiple:
    def test_multiple_errors(self):
        errors = validate_proposed_config(
            workers_cpu_ms=50,
            r2_storage_class="InfrequentAccess",
            do_backend="kv",
            enable_load_balancer=True,
        )
        assert len(errors) == 4
        assert all(e.startswith("ERROR:") for e in errors)

    def test_all_with_paid_override(self):
        assert validate_proposed_config(
            workers_cpu_ms=50,
            r2_storage_class="InfrequentAccess",
            do_backend="kv",
            enable_load_balancer=True,
            allow_paid_resources=True,
        ) == []
