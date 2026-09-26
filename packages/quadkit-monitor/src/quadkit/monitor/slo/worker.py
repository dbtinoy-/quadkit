"""Periodic worker that evaluates SLOs and dispatches alerts."""

from __future__ import annotations

from typing import TYPE_CHECKING

from quadkit.contracts.infra.tasks import OnErrorPolicy
from quadkit.logging import get_logger
from quadkit.monitor.scheduling import MonitorScheduledWorker
from quadkit.monitor.slo.monitor import SLOMonitor

if TYPE_CHECKING:
    from quadkit.contracts.infra.tasks import TaskManagerProtocol

logger = get_logger(__name__)


class SLOEvaluationWorker(MonitorScheduledWorker):
    """Periodically evaluates all registered SLOs and dispatches alerts.

    Extends :class:`~quadkit.monitor.scheduling.MonitorScheduledWorker` to run
    :meth:`~SLOMonitor.evaluate_and_dispatch` on a fixed interval.

    Usage::

        from quadkit.contracts.infra.tasks import TaskManagerProtocol

        worker = SLOEvaluationWorker(
            task_manager=task_manager,
            monitor=monitor,
            evaluation_interval=60.0,
        )
        await worker.start()
        # ...
        await worker.stop()
    """

    interval_seconds: float = 60.0
    initial_delay_seconds: float = 5.0
    on_error_policy: OnErrorPolicy = OnErrorPolicy.BACKOFF

    def __init__(
        self,
        task_manager: TaskManagerProtocol,
        monitor: SLOMonitor,
        *,
        evaluation_interval: float | None = None,
        initial_delay_seconds: float | None = None,
    ) -> None:
        super().__init__(
            task_manager,
            interval_seconds=evaluation_interval,
            initial_delay_seconds=initial_delay_seconds,
        )
        self._monitor = monitor

    @property
    def evaluation_interval(self) -> float:
        return self.interval_seconds

    async def run_cycle(self) -> None:
        """Evaluate SLOs and dispatch violations."""
        violations = await self._monitor.evaluate_and_dispatch()
        if violations:
            logger.info(
                "slo_cycle_complete",
                violation_count=len(violations),
            )


__all__ = ["SLOEvaluationWorker"]
