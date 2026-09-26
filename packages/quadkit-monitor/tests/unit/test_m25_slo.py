"""Tests for M25: SLO/SLOViolation/SLOMonitor."""

from datetime import datetime, timedelta, timezone

import pytest

from quadkit.monitor.slo.monitor import SLOMonitor
from quadkit.monitor.slo.objective import SLO, SLOViolation


class TestSLODataclass:
    """M25: SLO dataclass construction."""

    def test_defaults(self) -> None:
        """SLO has sensible defaults for optional fields."""
        slo = SLO(name="api_p99", metric="api.latency", percentile=0.99, threshold_ms=200.0)
        assert slo.window == timedelta(hours=1)
        assert slo.burn_rate_threshold == 1.0
        assert slo.description == ""

    def test_custom_window(self) -> None:
        """SLO accepts a custom sliding window."""
        slo = SLO(
            name="slow_slo",
            metric="db.query",
            percentile=0.95,
            threshold_ms=500.0,
            window=timedelta(minutes=30),
        )
        assert slo.window == timedelta(minutes=30)


class TestSLOViolation:
    """M25: SLOViolation auto-generates message."""

    def test_message_auto_generated(self) -> None:
        """SLOViolation __post_init__ populates message when not supplied."""
        slo = SLO(name="slo1", metric="m", percentile=0.99, threshold_ms=100.0)
        violation = SLOViolation(
            slo=slo,
            measured_value=250.0,
            burn_rate=2.5,
            detected_at=datetime.now(tz=timezone.utc),
        )
        assert violation.message != ""
        assert "slo1" in violation.message.lower() or "250" in violation.message

    def test_custom_message_preserved(self) -> None:
        """An explicit message is not overwritten."""
        slo = SLO(name="slo1", metric="m", percentile=0.99, threshold_ms=100.0)
        violation = SLOViolation(
            slo=slo,
            measured_value=250.0,
            burn_rate=2.5,
            detected_at=datetime.now(tz=timezone.utc),
            message="custom msg",
        )
        assert violation.message == "custom msg"


class TestSLOMonitor:
    """M25: SLOMonitor evaluation logic."""

    @pytest.fixture
    def monitor(self) -> SLOMonitor:
        return SLOMonitor()

    @pytest.fixture
    def simple_slo(self) -> SLO:
        return SLO(name="latency_p99", metric="api.latency", percentile=0.99, threshold_ms=100.0)

    def test_register_slo(self, monitor: SLOMonitor, simple_slo: SLO) -> None:
        """register() adds SLO to registered_slos."""
        monitor.register(simple_slo)
        assert "latency_p99" in monitor.registered_slos

    def test_duplicate_register_raises(self, monitor: SLOMonitor, simple_slo: SLO) -> None:
        """register() raises ValueError if SLO name is already registered."""
        monitor.register(simple_slo)
        with pytest.raises(ValueError):
            monitor.register(simple_slo)

    @pytest.mark.asyncio
    async def test_no_violations_when_below_threshold(
        self, monitor: SLOMonitor, simple_slo: SLO
    ) -> None:
        """evaluate() returns empty list when all samples are within SLO."""
        monitor.register(simple_slo)
        for _ in range(100):
            monitor.record_sample("api.latency", 50.0)
        violations = await monitor.evaluate()
        assert violations == []

    @pytest.mark.asyncio
    async def test_violation_when_p99_exceeds_threshold(
        self, monitor: SLOMonitor, simple_slo: SLO
    ) -> None:
        """evaluate() returns a violation when p99 exceeds threshold_ms."""
        monitor.register(simple_slo)
        # 98 fast samples + 2 slow ones so p99 (index 98 of 100) hits 999 ms
        for _ in range(98):
            monitor.record_sample("api.latency", 10.0)
        monitor.record_sample("api.latency", 999.0)
        monitor.record_sample("api.latency", 999.0)

        violations = await monitor.evaluate()
        assert len(violations) == 1
        assert isinstance(violations[0], SLOViolation)
        assert violations[0].slo.name == "latency_p99"

    @pytest.mark.asyncio
    async def test_clear_samples_removes_metric(
        self, monitor: SLOMonitor, simple_slo: SLO
    ) -> None:
        """clear_samples() removes recorded samples for the specified metric."""
        monitor.register(simple_slo)
        monitor.record_sample("api.latency", 999.0)
        monitor.clear_samples("api.latency")
        violations = await monitor.evaluate()
        assert violations == []

    @pytest.mark.asyncio
    async def test_evaluate_no_samples(self, monitor: SLOMonitor, simple_slo: SLO) -> None:
        """evaluate() returns no violations when there are no samples."""
        monitor.register(simple_slo)
        violations = await monitor.evaluate()
        assert violations == []
