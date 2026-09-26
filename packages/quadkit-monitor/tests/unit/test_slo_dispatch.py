"""Tests for SLOMonitor.evaluate_and_dispatch() and suppression."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from quadkit.contracts.monitor.projection_tier import ProjectionTier
from quadkit.contracts.observability.metrics import AlertDispatcherProtocol
from quadkit.monitor.slo.monitor import SLOMonitor
from quadkit.monitor.slo.objective import SLO


class TestSLOMonitorDispatch:
    @pytest.fixture()
    def alert_dispatcher(self) -> AsyncMock:
        d = AsyncMock(spec=AlertDispatcherProtocol)
        d.send_metric_alert = AsyncMock()
        return d

    @pytest.fixture()
    def monitor(self, alert_dispatcher: AsyncMock) -> SLOMonitor:
        return SLOMonitor(alert_dispatcher=alert_dispatcher)

    def _setup_slo_with_violation(
        self,
        monitor: SLOMonitor,
        tier: ProjectionTier = ProjectionTier.P1_BUSINESS_HOURS,
    ) -> SLO:
        slo = SLO(
            name="violated_slo",
            metric="test.metric",
            percentile=0.99,
            threshold_ms=100.0,
            window=timedelta(hours=1),
            tier=tier,
            owner="team-a",
            runbook_url="https://ops.runbook/slo",
        )
        monitor.register(slo)
        for _ in range(100):
            monitor.record_sample("test.metric", 200.0)
        return slo

    @pytest.mark.asyncio
    async def test_evaluate_and_dispatch_sends_metric_alert(
        self,
        monitor: SLOMonitor,
        alert_dispatcher: AsyncMock,
    ):
        slo = self._setup_slo_with_violation(monitor)

        violations = await monitor.evaluate_and_dispatch()

        assert len(violations) == 1
        alert_dispatcher.send_metric_alert.assert_awaited_once()
        call_kwargs = alert_dispatcher.send_metric_alert.await_args.kwargs
        assert call_kwargs["metric_name"] == "test.metric"
        assert call_kwargs["context"]["tier"] == "p1_business_hours"
        assert call_kwargs["context"]["slo_name"] == "violated_slo"
        assert call_kwargs["context"]["owner"] == "team-a"
        assert call_kwargs["context"]["runbook_url"] == "https://ops.runbook/slo"

    @pytest.mark.asyncio
    async def test_no_alert_when_no_violations(
        self,
        monitor: SLOMonitor,
        alert_dispatcher: AsyncMock,
    ):
        slo = SLO(
            name="ok_slo",
            metric="ok.metric",
            percentile=0.99,
            threshold_ms=500.0,
        )
        monitor.register(slo)
        monitor.record_sample("ok.metric", 100.0)

        violations = await monitor.evaluate_and_dispatch()

        assert len(violations) == 0
        alert_dispatcher.send_metric_alert.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_suppression_window_prevents_duplicate_alerts(
        self,
        alert_dispatcher: AsyncMock,
    ):
        monitor = SLOMonitor(
            alert_dispatcher=alert_dispatcher,
            suppression_window_seconds=300,
        )
        self._setup_slo_with_violation(monitor)

        # First call — should dispatch
        await monitor.evaluate_and_dispatch()
        assert alert_dispatcher.send_metric_alert.await_count == 1

        # Second call immediately after — should be suppressed
        await monitor.evaluate_and_dispatch()
        assert alert_dispatcher.send_metric_alert.await_count == 1

    @pytest.mark.asyncio
    async def test_no_dispatcher_does_not_crash(
        self,
    ):
        monitor = SLOMonitor()  # no alert_dispatcher
        self._setup_slo_with_violation(monitor)

        violations = await monitor.evaluate_and_dispatch()

        assert len(violations) == 1  # violations still reported

    @pytest.mark.asyncio
    async def test_p0_tier_in_context(
        self,
        monitor: SLOMonitor,
        alert_dispatcher: AsyncMock,
    ):
        self._setup_slo_with_violation(monitor, tier=ProjectionTier.P0_PAGE)

        await monitor.evaluate_and_dispatch()

        context = alert_dispatcher.send_metric_alert.await_args.kwargs["context"]
        assert context["tier"] == "p0_page"
