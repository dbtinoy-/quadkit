"""Tests for SLOEvaluationWorker."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from quadkit.contracts.observability.metrics import AlertDispatcherProtocol
from quadkit.monitor.slo.monitor import SLOMonitor
from quadkit.monitor.slo.worker import SLOEvaluationWorker
from quadkit.tasks.background_task_manager import BackgroundTaskManager


@pytest.fixture
def task_manager() -> BackgroundTaskManager:
    return BackgroundTaskManager()


@pytest.fixture
def alert_dispatcher() -> AsyncMock:
    d = AsyncMock(spec=AlertDispatcherProtocol)
    d.send_metric_alert = AsyncMock()
    return d


@pytest.fixture
def monitor(alert_dispatcher: AsyncMock) -> SLOMonitor:
    return SLOMonitor(alert_dispatcher=alert_dispatcher)


class TestSLOEvaluationWorker:
    @pytest.mark.asyncio
    async def test_run_cycle_calls_evaluate_and_dispatch(
        self,
        task_manager: BackgroundTaskManager,
        monitor: SLOMonitor,
        alert_dispatcher: AsyncMock,
    ):
        """Worker calls evaluate_and_dispatch on each cycle."""
        monitor.evaluate_and_dispatch = AsyncMock(return_value=[])

        worker = SLOEvaluationWorker(
            task_manager=task_manager,
            monitor=monitor,
        )
        await worker.run_cycle()

        monitor.evaluate_and_dispatch.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_start_and_stop(
        self,
        task_manager: BackgroundTaskManager,
        monitor: SLOMonitor,
    ):
        """Worker can be started and stopped cleanly."""
        monitor.evaluate_and_dispatch = AsyncMock(return_value=[])

        worker = SLOEvaluationWorker(
            task_manager=task_manager,
            monitor=monitor,
            evaluation_interval=0.05,
            initial_delay_seconds=0.0,
        )

        await worker.start()
        await asyncio.sleep(0.12)
        await worker.stop()

        assert monitor.evaluate_and_dispatch.await_count >= 1

    @pytest.mark.asyncio
    async def test_default_interval(
        self,
        task_manager: BackgroundTaskManager,
        monitor: SLOMonitor,
    ):
        """Default evaluation interval is 60 seconds."""
        worker = SLOEvaluationWorker(
            task_manager=task_manager,
            monitor=monitor,
        )
        assert worker.evaluation_interval == 60.0

    @pytest.mark.asyncio
    async def test_custom_interval(
        self,
        task_manager: BackgroundTaskManager,
        monitor: SLOMonitor,
    ):
        """Custom evaluation interval is accepted."""
        worker = SLOEvaluationWorker(
            task_manager=task_manager,
            monitor=monitor,
            evaluation_interval=120.0,
        )
        assert worker.evaluation_interval == 120.0

    @pytest.mark.asyncio
    async def test_with_alert_dispatcher_routes_violations(
        self,
        task_manager: BackgroundTaskManager,
        alert_dispatcher: AsyncMock,
    ):
        """Worker routes SLO violations through the alert dispatcher."""
        from datetime import timedelta

        from quadkit.monitor.slo.objective import SLO

        monitor = SLOMonitor(alert_dispatcher=alert_dispatcher)
        slo = SLO(
            name="latency",
            metric="p99",
            percentile=0.99,
            threshold_ms=50.0,
            window=timedelta(hours=1),
        )
        monitor.register(slo)
        for _ in range(100):
            monitor.record_sample("p99", 200.0)

        worker = SLOEvaluationWorker(
            task_manager=task_manager,
            monitor=monitor,
            evaluation_interval=0.05,
        )

        await worker.run_cycle()
        alert_dispatcher.send_metric_alert.assert_awaited_once()
