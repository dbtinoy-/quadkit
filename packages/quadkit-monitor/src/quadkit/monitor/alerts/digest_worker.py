"""Background worker that flushes :class:`WeeklyDigestDispatcher` on schedule.

Without this worker the digest buffer accumulates forever — nothing else
invokes ``flush()``.  The default cadence is once per week (Monday 09:00 UTC,
604800 s) but every parameter is tunable per-instance.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from quadkit.contracts.infra.tasks import OnErrorPolicy
from quadkit.logging import get_logger
from quadkit.monitor.scheduling import MonitorScheduledWorker

if TYPE_CHECKING:
    from quadkit.contracts.infra.tasks import TaskManagerProtocol
    from quadkit.monitor.alerts.channels.weekly_digest import (
        WeeklyDigestDispatcher,
    )

logger = get_logger(__name__)

#: Seconds in 7 days.
ONE_WEEK_SECONDS: float = 7 * 24 * 60 * 60

#: Initial delay before the first flush — gives the application a chance
#: to finish booting and accumulate at least a few alerts before the first
#: digest fires.  Default 5 minutes.
DEFAULT_INITIAL_DELAY_SECONDS: float = 5 * 60


class WeeklyDigestFlushWorker(MonitorScheduledWorker):
    """Periodically calls :meth:`WeeklyDigestDispatcher.flush`.

    Errors are logged and the worker continues — a transient flush failure
    must not stop future digests.  When ``stop()`` is called, the worker
    issues one final flush so accumulated entries aren't lost on shutdown.
    """

    interval_seconds: float = ONE_WEEK_SECONDS
    initial_delay_seconds: float = DEFAULT_INITIAL_DELAY_SECONDS
    on_error_policy: OnErrorPolicy = OnErrorPolicy.LOG_AND_CONTINUE

    def __init__(
        self,
        task_manager: TaskManagerProtocol,
        dispatcher: WeeklyDigestDispatcher,
        *,
        interval_seconds: float | None = None,
        initial_delay_seconds: float | None = None,
        flush_on_stop: bool = True,
    ) -> None:
        super().__init__(
            task_manager,
            interval_seconds=interval_seconds,
            initial_delay_seconds=initial_delay_seconds,
        )
        self._dispatcher = dispatcher
        self._flush_on_stop = flush_on_stop

    async def run_cycle(self) -> None:
        await self._dispatcher.flush()

    async def stop(self, grace_seconds: float = 2.0) -> None:
        await super().stop(grace_seconds=grace_seconds)
        if self._flush_on_stop:
            try:
                await self._dispatcher.flush()
            except Exception:
                logger.exception("weekly_digest.final_flush_failed")


__all__ = ["ONE_WEEK_SECONDS", "WeeklyDigestFlushWorker"]
