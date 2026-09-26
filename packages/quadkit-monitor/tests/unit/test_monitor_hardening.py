"""Round-7 hardening tests for quadkit-monitor alert/health paths."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.contracts.core import HealthCheckResult, HealthStatus
from quadkit.contracts.core.health import HealthCheckCategory
from quadkit.monitor.alerts.channels.pagerduty import PagerDutyAlertDispatcher
from quadkit.monitor.alerts.channels.weekly_digest import WeeklyDigestDispatcher
from quadkit.monitor.health.cached import CachedHealthChecker
from quadkit.monitor.health.checker import HealthChecker
from quadkit.monitor.health.checker_registry import HealthCheckerRegistry
from quadkit.monitor.slo.monitor import SLOMonitor
from quadkit.monitor.slo.objective import SLO


class _Result:
    """Minimal Result wrapper matching CacheBackendProtocol.get()."""

    def __init__(self, value):
        self._value = value

    def unwrap_or(self, default):
        return self._value if self._value is not None else default


class _FakeCache:
    """CacheBackendProtocol double with observable set/get/delete."""

    def __init__(self):
        self.store: dict[str, str] = {}
        self.set_count = 0

    async def get(self, key):
        return _Result(self.store.get(key))

    async def set(self, key, value, *args, **kwargs):
        self.set_count += 1
        self.store[key] = value
        return _Result(True)

    async def delete(self, key):
        self.store.pop(key, None)
        return _Result(True)


class TestSLOPercentileNearestRank:
    """p-th percentile = value at rank ceil(p*N) (1-based)."""

    def test_p95_of_21_samples_uses_ceiling_rank(self) -> None:
        # 21 samples 1..21: rank = ceil(0.95*21) = ceil(19.95) = 20 → value 20.
        monitor = SLOMonitor()
        for i in range(1, 22):
            monitor.record_sample("m", float(i))
        assert monitor._compute_percentile([float(i) for i in range(1, 22)], 0.95) == 20.0

    def test_p99_of_100_samples(self) -> None:
        monitor = SLOMonitor()
        assert monitor._compute_percentile([float(i) for i in range(1, 101)], 0.99) == 99.0

    def test_percentile_of_empty_list_is_zero(self) -> None:
        monitor = SLOMonitor()
        assert monitor._compute_percentile([], 0.99) == 0.0


class TestSLOWindowRolling:
    """SLO.window must restrict evaluation to samples inside the window."""

    @pytest.mark.asyncio
    async def test_stale_samples_outside_window_are_ignored(self) -> None:
        monitor = SLOMonitor()
        monitor.register(
            SLO(
                name="stale",
                metric="m",
                percentile=0.99,
                threshold_ms=100.0,
                window=timedelta(hours=1),
            )
        )
        now = datetime.now(tz=UTC)
        # Violating sample from 2 hours ago — outside the 1h window.
        monitor.record_sample("m", 999.0, at=now - timedelta(hours=2))
        # Healthy recent sample inside the window.
        monitor.record_sample("m", 10.0, at=now - timedelta(minutes=1))

        assert await monitor.evaluate() == []

    @pytest.mark.asyncio
    async def test_violation_inside_window_still_fires(self) -> None:
        monitor = SLOMonitor()
        monitor.register(
            SLO(
                name="fresh",
                metric="m",
                percentile=0.99,
                threshold_ms=100.0,
                window=timedelta(hours=1),
            )
        )
        now = datetime.now(tz=UTC)
        monitor.record_sample("m", 999.0, at=now - timedelta(minutes=5))

        violations = await monitor.evaluate()
        assert len(violations) == 1
        assert violations[0].slo.name == "fresh"

    @pytest.mark.asyncio
    async def test_window_expiry_clears_violation(self) -> None:
        # Same samples as above, but a 30-minute window excludes the breach.
        monitor = SLOMonitor()
        monitor.register(
            SLO(
                name="narrow",
                metric="m",
                percentile=0.99,
                threshold_ms=100.0,
                window=timedelta(minutes=30),
            )
        )
        now = datetime.now(tz=UTC)
        monitor.record_sample("m", 999.0, at=now - timedelta(minutes=45))
        monitor.record_sample("m", 10.0, at=now - timedelta(minutes=5))

        violations = await monitor.evaluate()
        assert violations == []


class TestHealthCheckerCategorySubset:
    """run_liveness/readiness/startup must not disturb run_all()."""

    def _make_checker(self) -> HealthChecker:
        checker = HealthChecker()
        checker.add("live", lambda: True, category=HealthCheckCategory.LIVENESS)
        checker.add("ready", lambda: True, category=HealthCheckCategory.READINESS)
        return checker

    @pytest.mark.asyncio
    async def test_run_all_after_category_run_keeps_every_check(self) -> None:
        checker = self._make_checker()
        _, liveness = await checker.run_liveness()
        assert set(liveness) == {"live"}

        all_results = await checker.run_all()
        assert set(all_results) == {"live", "ready"}

    @pytest.mark.asyncio
    async def test_run_all_only_filters_explicitly(self) -> None:
        checker = self._make_checker()
        results = await checker.run_all(only={"ready"})
        assert set(results) == {"ready"}


class TestWeeklyDigestConcurrentAppends:
    """Concurrent alerts in one process must not lose entries."""

    @pytest.mark.asyncio
    async def test_gathered_appends_all_persist(self) -> None:
        cache = _FakeCache()
        flusher = AsyncMock()
        flusher.send_alert = AsyncMock()
        dispatcher = WeeklyDigestDispatcher(
            buffer_store=cache,  # type: ignore[arg-type]
            flush_dispatcher=flusher,  # type: ignore[arg-type]
        )

        async def send(i: int) -> None:
            await dispatcher.send_alert(f"t{i}", f"m{i}", "low")

        await asyncio.gather(*(send(i) for i in range(20)))
        assert cache.set_count == 20

        raw = cache.store.get("monitor:weekly_digest")
        assert raw is not None
        from quadkit.serialization import loads

        entries = loads(raw)
        assert len(entries) == 20


class TestPagerDutyDedupKey:
    """Recurring alert types must share a stable dedup_key."""

    def _dispatcher(self) -> PagerDutyAlertDispatcher:
        http = MagicMock()
        return PagerDutyAlertDispatcher(integration_key="k", http_client=http)  # type: ignore[arg-type]

    def test_dedup_key_present_and_stable(self) -> None:
        d = self._dispatcher()
        p1 = d._build_payload("Metric breach: cpu", "90% (threshold: 80%)", "high", None)
        p2 = d._build_payload("Metric breach: cpu", "95% (threshold: 80%)", "high", None)
        key1 = p1["payload"]["dedup_key"]
        key2 = p2["payload"]["dedup_key"]
        assert key1 == key2  # same title → same incident
        assert key1.startswith("quadkit-")
        assert len(key1) == len("quadkit-") + 24

    def test_dedup_key_differs_per_title(self) -> None:
        d = self._dispatcher()
        p1 = d._build_payload("A", "x", "low", None)
        p2 = d._build_payload("B", "x", "low", None)
        assert p1["payload"]["dedup_key"] != p2["payload"]["dedup_key"]


class TestRegistryCacheBackendPassthrough:
    def test_get_or_create_passes_cache_backend(self) -> None:
        registry = HealthCheckerRegistry()
        backend = MagicMock()
        checker = registry.get_or_create("api", cache_backend=backend)
        assert checker._cache_backend is backend  # type: ignore[attr-defined]

    def test_get_or_create_default_cache_backend_none(self) -> None:
        registry = HealthCheckerRegistry()
        checker = registry.get_or_create("api")
        assert checker._cache_backend is None  # type: ignore[attr-defined]


class TestRedisHealthNoBackend:
    @pytest.mark.asyncio
    async def test_no_cache_backend_reports_unhealthy(self) -> None:
        checker = CachedHealthChecker(cache_backend=None)
        result = await checker.get_redis_health()
        assert result.status == HealthStatus.UNHEALTHY
        assert "No cache backend configured" in (result.message or "")

    @pytest.mark.asyncio
    async def test_configured_healthy_backend_reports_healthy(self) -> None:
        backend = MagicMock()
        backend.health_check = AsyncMock(
            return_value=HealthCheckResult(
                component="redis", status=HealthStatus.HEALTHY
            )
        )
        checker = CachedHealthChecker(cache_backend=backend)  # type: ignore[arg-type]
        result = await checker.get_redis_health()
        assert result.status == HealthStatus.HEALTHY
        backend.health_check.assert_awaited_once()


class _SLODispatcher:
    """Dispatcher that only records sends."""

    def __init__(self) -> None:
        self.sends: list[dict] = []

    async def send_alert(self, title, message, severity, context=None):
        self.sends.append({"kind": "alert", "title": title, "severity": severity})

    async def send_metric_alert(self, metric_name, current_value, threshold, context=None):
        self.sends.append({"kind": "metric", "metric": metric_name})


class TestSuppressionAcrossRecovery:
    """After recovery + re-breach beyond the window, alerts fire again."""

    @pytest.mark.asyncio
    async def test_realert_after_suppression_window(self) -> None:
        dispatcher = _SLODispatcher()
        monitor = SLOMonitor(alert_dispatcher=dispatcher, suppression_window_seconds=100)
        monitor.register(
            SLO(name="s", metric="m", percentile=0.99, threshold_ms=100.0)
        )
        monitor.record_sample("m", 500.0)

        assert await monitor.evaluate_and_dispatch()
        assert len(dispatcher.sends) == 1
        # Still within the suppression window → suppressed.
        await monitor.evaluate_and_dispatch()
        assert len(dispatcher.sends) == 1

        # Move the last-dispatched timestamp back beyond the window.
        last = monitor._last_dispatched["s"]
        monitor._last_dispatched["s"] = last - timedelta(seconds=101)
        violations = await monitor.evaluate_and_dispatch()
        assert len(violations) == 1
        assert len(dispatcher.sends) == 2
