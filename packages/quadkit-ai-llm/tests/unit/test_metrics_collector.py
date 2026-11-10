"""Tests for the LLM metrics collector (was 0% covered — round 77)."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from quadkit.ai.llm.metrics import (
    CacheMetrics,
    ErrorMetrics,
    MetricsCollector,
    MetricType,
    TimingMetrics,
    UsageMetrics,
)
from quadkit.ai.llm.metrics import collector as metrics_collector

# ---------------------------------------------------------------------------
# TimingMetrics
# ---------------------------------------------------------------------------


class TestTimingMetrics:
    def test_record_latency_updates_counts_and_bounds(self) -> None:
        tm = TimingMetrics(provider="p", model_id="m")
        tm.record_latency(100.0)
        tm.record_latency(50.0)
        tm.record_latency(75.0)

        assert tm.request_count == 3
        assert tm.min_latency_ms == 50.0
        assert tm.max_latency_ms == 100.0
        assert tm.avg_latency_ms == pytest.approx(75.0)

    def test_total_requests_is_live_alias(self) -> None:
        """total_requests must track request_count (was frozen at 0)."""
        tm = TimingMetrics(provider="p", model_id="m")
        assert tm.total_requests == 0

        tm.record_latency(10.0)
        tm.record_latency(20.0)

        assert tm.total_requests == 2
        assert tm.total_requests == tm.request_count

    def test_percentiles_stay_zero_below_20_samples(self) -> None:
        tm = TimingMetrics(provider="p", model_id="m")
        for i in range(1, 20):
            tm.record_latency(float(i))

        assert tm.p95_latency_ms == 0.0
        assert tm.p99_latency_ms == 0.0

    def test_percentiles_populated_at_20_samples(self) -> None:
        tm = TimingMetrics(provider="p", model_id="m")
        for i in range(1, 21):
            tm.record_latency(float(i))

        # sorted[19] (int(20*0.95)=19) = 20.0; sorted[19] (int(20*0.99)=19) = 20.0
        assert tm.p95_latency_ms == 20.0
        assert tm.p99_latency_ms == 20.0
        assert tm.p95_latency_ms <= tm.p99_latency_ms

    def test_zero_latency_recorded(self) -> None:
        tm = TimingMetrics(provider="p", model_id="m")
        tm.record_latency(0.0)
        tm.record_latency(10.0)

        assert tm.min_latency_ms == 0.0
        assert tm.request_count == 2


# ---------------------------------------------------------------------------
# ErrorMetrics
# ---------------------------------------------------------------------------


class TestErrorMetrics:
    def test_error_rate_zero_when_no_requests(self) -> None:
        em = ErrorMetrics(provider="p", model_id="m")
        assert em.error_rate == 0.0

    def test_error_rate_percentage(self) -> None:
        em = ErrorMetrics(provider="p", model_id="m")
        for _ in range(4):
            em.record_request()
        em.record_error("timeout")
        em.record_error("rate_limit")

        assert em.error_rate == pytest.approx(50.0)
        assert em.timeout_errors == 1
        assert em.rate_limit_errors == 1

    @pytest.mark.parametrize(
        ("error_type", "attribute"),
        [
            ("rate_limit", "rate_limit_errors"),
            ("timeout", "timeout_errors"),
            ("auth", "auth_errors"),
            ("other", "other_errors"),
            ("unknown_thing", "other_errors"),
        ],
    )
    def test_error_classification(self, error_type: str, attribute: str) -> None:
        em = ErrorMetrics(provider="p", model_id="m")
        em.record_error(error_type)

        assert em.error_count == 1
        assert getattr(em, attribute) == 1


# ---------------------------------------------------------------------------
# CacheMetrics / UsageMetrics
# ---------------------------------------------------------------------------


class TestCacheAndUsage:
    def test_hit_rate_zero_when_empty(self) -> None:
        assert CacheMetrics().hit_rate == 0.0

    def test_hit_rate_50_50(self) -> None:
        cm = CacheMetrics(cache_hits=1, cache_misses=1)
        assert cm.hit_rate == pytest.approx(50.0)

    def test_usage_total_tokens(self) -> None:
        um = UsageMetrics(
            provider="p", model_id="m", prompt_tokens=10, completion_tokens=5
        )
        assert um.total_tokens == 15


# ---------------------------------------------------------------------------
# MetricsCollector
# ---------------------------------------------------------------------------


class TestMetricsCollector:
    def test_debug_log_omits_provider_and_model_identifiers(self, monkeypatch) -> None:
        """Provider and model identifiers stay in metrics storage, not logs."""
        log = Mock()
        monkeypatch.setattr(metrics_collector, "logger", log)
        collector = MetricsCollector()
        private_provider = "private-provider-alias-7f31"
        private_model_id = "private-model-alias-7f31"

        collector.record_request(private_provider, private_model_id, latency_ms=10.0)

        log.debug.assert_called_once_with(
            "metrics_recorded",
            latency_ms=10.0,
            error=False,
        )
        assert private_provider not in repr(log.debug.call_args)
        assert private_model_id not in repr(log.debug.call_args)
        assert (
            collector.get_timing_metrics(private_provider, private_model_id) is not None
        )

    def test_getters_return_none_for_unknown(self) -> None:
        collector = MetricsCollector()
        assert collector.get_timing_metrics("p", "m") is None
        assert collector.get_error_metrics("p", "m") is None
        assert collector.get_usage_metrics("p", "m") is None
        assert collector.get_cache_metrics() == {}

    def test_record_request_creates_entries(self) -> None:
        collector = MetricsCollector()
        collector.record_request("p", "m", latency_ms=100.0)

        timing = collector.get_timing_metrics("p", "m")
        assert timing is not None
        assert timing.request_count == 1

        errors = collector.get_error_metrics("p", "m")
        assert errors is not None
        assert errors.total_requests == 1
        assert errors.error_count == 0

    def test_record_request_with_error(self) -> None:
        collector = MetricsCollector()
        collector.record_request(
            "p", "m", latency_ms=10.0, error=True, error_type="auth"
        )

        errors = collector.get_error_metrics("p", "m")
        assert errors is not None
        assert errors.error_count == 1
        assert errors.auth_errors == 1

    def test_record_request_error_defaults_to_other(self) -> None:
        collector = MetricsCollector()
        collector.record_request("p", "m", latency_ms=10.0, error=True)

        errors = collector.get_error_metrics("p", "m")
        assert errors is not None
        assert errors.other_errors == 1

    def test_usage_accumulates(self) -> None:
        collector = MetricsCollector()
        collector.record_request(
            "p",
            "m",
            latency_ms=10.0,
            prompt_tokens=100,
            completion_tokens=50,
            cost_usd=0.01,
        )
        collector.record_request(
            "p",
            "m",
            latency_ms=10.0,
            prompt_tokens=30,
            completion_tokens=20,
            cost_usd=0.02,
        )

        usage = collector.get_usage_metrics("p", "m")
        assert usage is not None
        assert usage.prompt_tokens == 130
        assert usage.completion_tokens == 70
        assert usage.total_tokens == 200
        assert usage.cost_usd == pytest.approx(0.03)

    def test_usage_entry_exists_without_usage_data(self) -> None:
        collector = MetricsCollector()
        collector.record_request("p", "m", latency_ms=10.0)

        usage = collector.get_usage_metrics("p", "m")
        assert usage is not None
        assert usage.total_tokens == 0

    def test_cache_hit_and_miss(self) -> None:
        collector = MetricsCollector()
        collector.record_cache_hit("p", tokens_saved=100)
        collector.record_cache_hit("p", tokens_saved=50)
        collector.record_cache_miss("p")

        cache = collector.get_cache_metrics()["p"]
        assert cache.cache_hits == 2
        assert cache.cache_misses == 1
        assert cache.tokens_saved == 150
        assert cache.hit_rate == pytest.approx(66.666, abs=0.01)


# ---------------------------------------------------------------------------
# Snapshots
# ---------------------------------------------------------------------------


class TestSnapshots:
    def test_latency_snapshot_is_weighted_by_requests(self) -> None:
        """A 1-request 1000ms model must not drag a 100-request 10ms
        model's provider average to ~500ms (old unweighted mean)."""
        collector = MetricsCollector()
        for _ in range(100):
            collector.record_request("p", "big", latency_ms=10.0)
        collector.record_request("p", "tiny", latency_ms=1000.0)

        collector.take_snapshot("p", MetricType.LATENCY)

        snapshot = collector.get_snapshots("p", MetricType.LATENCY)[0]
        assert snapshot.data["request_count"] == 101
        # weighted: (100*10 + 1*1000)/101 = 19.80...
        assert snapshot.data["avg_latency_ms"] == pytest.approx(19.80, abs=0.01)

    def test_error_snapshot_aggregates(self) -> None:
        collector = MetricsCollector()
        collector.record_request("p", "a", latency_ms=10.0)
        collector.record_request("p", "b", latency_ms=10.0, error=True)

        collector.take_snapshot("p", MetricType.ERROR)

        snapshot = collector.get_snapshots("p", MetricType.ERROR)[0]
        assert snapshot.data["total_requests"] == 2
        assert snapshot.data["error_count"] == 1
        assert snapshot.data["error_rate"] == pytest.approx(50.0)

    def test_cache_snapshot(self) -> None:
        collector = MetricsCollector()
        collector.record_cache_hit("p", tokens_saved=10)
        collector.record_cache_miss("p")

        collector.take_snapshot("p", MetricType.CACHE)

        snapshot = collector.get_snapshots("p", MetricType.CACHE)[0]
        assert snapshot.data["hits"] == 1
        assert snapshot.data["misses"] == 1
        assert snapshot.data["hit_rate"] == pytest.approx(50.0)
        assert snapshot.data["tokens_saved"] == 10

    def test_token_usage_snapshot(self) -> None:
        collector = MetricsCollector()
        collector.record_request(
            "p", "a", latency_ms=10.0, prompt_tokens=100, completion_tokens=50
        )

        collector.take_snapshot("p", MetricType.TOKEN_USAGE)

        snapshot = collector.get_snapshots("p", MetricType.TOKEN_USAGE)[0]
        assert snapshot.data["prompt_tokens"] == 100
        assert snapshot.data["completion_tokens"] == 50
        assert snapshot.data["total_tokens"] == 150

    def test_cost_snapshot(self) -> None:
        collector = MetricsCollector()
        collector.record_request("p", "a", latency_ms=10.0, cost_usd=0.000001)
        collector.record_request("p", "a", latency_ms=10.0, cost_usd=0.000001)

        collector.take_snapshot("p", MetricType.COST)

        snapshot = collector.get_snapshots("p", MetricType.COST)[0]
        assert snapshot.data["cost_usd"] == pytest.approx(0.000002)

    def test_snapshot_no_data_records_nothing(self) -> None:
        collector = MetricsCollector()

        collector.take_snapshot("nobody", MetricType.LATENCY)

        assert collector.get_snapshots() == []

    def test_get_snapshots_filters(self) -> None:
        collector = MetricsCollector()
        collector.record_request("p1", "a", latency_ms=10.0)
        collector.record_request("p2", "a", latency_ms=10.0)

        collector.take_snapshot("p1", MetricType.LATENCY)
        collector.take_snapshot("p2", MetricType.LATENCY)
        collector.take_snapshot("p1", MetricType.ERROR)

        assert len(collector.get_snapshots()) == 3
        assert len(collector.get_snapshots("p1")) == 2
        assert len(collector.get_snapshots("p1", MetricType.LATENCY)) == 1
        assert len(collector.get_snapshots("p3")) == 0
        # returned list is a copy — mutating it must not affect the collector
        snapshots = collector.get_snapshots()
        snapshots.clear()
        assert len(collector.get_snapshots()) == 3


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


class TestSummary:
    def test_get_summary_structure(self) -> None:
        collector = MetricsCollector()
        collector.record_request(
            "p", "m", latency_ms=100.0, error=True, error_type="timeout"
        )
        collector.record_request("p", "m", latency_ms=50.0)
        collector.record_cache_hit("p", tokens_saved=7)

        summary = collector.get_summary()

        assert summary["uptime_seconds"] >= 0
        assert summary["timing_metrics"]["p:m"]["requests"] == 2
        assert summary["timing_metrics"]["p:m"]["avg_latency_ms"] == pytest.approx(75.0)
        assert summary["error_metrics"]["p:m"]["total_requests"] == 2
        assert summary["error_metrics"]["p:m"]["error_rate"] == pytest.approx(50.0)
        assert summary["cache_metrics"]["p"]["tokens_saved"] == 7


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------


class TestExports:
    def test_subpackage_exports(self) -> None:
        import quadkit.ai.llm.metrics as metrics_pkg

        for name in (
            "CacheMetrics",
            "ErrorMetrics",
            "MetricType",
            "MetricsCollector",
            "MetricsSnapshot",
            "TimingMetrics",
            "UsageMetrics",
        ):
            assert name in metrics_pkg.__all__
            assert hasattr(metrics_pkg, name)

    def test_package_level_lazy_export(self) -> None:
        from quadkit.ai.llm import MetricsCollector as PackageCollector

        assert PackageCollector is MetricsCollector
