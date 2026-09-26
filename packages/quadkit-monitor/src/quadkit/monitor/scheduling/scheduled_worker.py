"""Periodic worker base class for monitor background loops.

Monitor-side implementation of the shared scheduled-worker pattern.  The
scheduling loop runs against
:class:`~quadkit.contracts.infra.tasks.TaskManagerProtocol` (resolved from
the container) so that ``quadkit.monitor`` never imports ``quadkit.tasks``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
import random
from typing import TYPE_CHECKING

from quadkit.contracts.infra.tasks import OnErrorPolicy
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.contracts.infra.tasks import TaskManagerProtocol

logger = get_logger(__name__)


class MonitorScheduledWorker(ABC):
    """Periodic worker base class.

    Subclass and implement :meth:`run_cycle`.  The base class handles the
    scheduling loop, error policy, graceful shutdown, and task tracking via
    :class:`~quadkit.contracts.infra.tasks.TaskManagerProtocol`.

    Class-level defaults (override per subclass or via constructor)::

        class DigestFlushWorker(MonitorScheduledWorker):
            interval_seconds = 604800.0
            on_error_policy = OnErrorPolicy.LOG_AND_CONTINUE

        worker = DigestFlushWorker(
            task_manager=task_manager,
            on_error_policy=OnErrorPolicy.LOG_AND_CONTINUE,
        )
        await worker.start()
        # ...
        await worker.stop()
    """

    #: Seconds between the end of one cycle and the start of the next.
    interval_seconds: float = 60.0

    #: Extra wait before the very first cycle.  Zero means start immediately.
    initial_delay_seconds: float = 0.0

    #: Upper bound for random jitter added to each sleep.  Zero disables.
    max_jitter_seconds: float = 0.0

    #: What to do when :meth:`run_cycle` raises an exception.
    on_error_policy: OnErrorPolicy = OnErrorPolicy.LOG_AND_CONTINUE

    def __init__(
        self,
        task_manager: TaskManagerProtocol,
        *,
        interval_seconds: float | None = None,
        initial_delay_seconds: float | None = None,
        max_jitter_seconds: float | None = None,
        on_error_policy: OnErrorPolicy | None = None,
    ) -> None:
        """Initialise the worker.

        Args:
            task_manager: Shared task manager that owns the task handle and
                participates in framework shutdown.
            interval_seconds: Override :attr:`interval_seconds`.
            initial_delay_seconds: Override :attr:`initial_delay_seconds`.
            max_jitter_seconds: Override :attr:`max_jitter_seconds`.
            on_error_policy: Override :attr:`on_error_policy`.
        """
        self._task_manager = task_manager

        if interval_seconds is not None:
            self.interval_seconds = interval_seconds
        if initial_delay_seconds is not None:
            self.initial_delay_seconds = initial_delay_seconds
        if max_jitter_seconds is not None:
            self.max_jitter_seconds = max_jitter_seconds
        if on_error_policy is not None:
            self.on_error_policy = on_error_policy

        self._stop_event: asyncio.Event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Start the worker loop as a tracked background task.

        Safe to call only once.  Calling ``start()`` while already running
        is a no-op (logs a warning).
        """
        if self._task is not None and not self._task.done():
            logger.warning(
                "scheduled_worker.already_running",
                worker=type(self).__name__,
            )
            return

        self._stop_event.clear()
        worker_name = f"scheduled_worker.{type(self).__name__}"
        self._task = self._task_manager.track_named(worker_name, self._run_loop())
        logger.info("worker_started", worker=type(self).__name__)

    async def stop(self, grace_seconds: float = 2.0) -> None:
        """Signal the worker to stop and wait for it to finish.

        Graceful: the stop event is set so the sleeping phase wakes up early,
        and the current cycle (if any) is allowed to finish.  If the task has
        not completed within *grace_seconds*, it is forcibly cancelled.

        Args:
            grace_seconds: Seconds to wait for a clean stop before cancelling.
        """
        self._stop_event.set()

        if self._task is None or self._task.done():
            return

        try:
            await asyncio.wait_for(asyncio.shield(self._task), timeout=grace_seconds)
        except (TimeoutError, asyncio.CancelledError):
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):  # noqa: S110 — intentional best-effort fallback
                pass

        logger.info("worker_stopped", worker=type(self).__name__)

    @abstractmethod
    async def run_cycle(self) -> None:
        """Override to implement one unit of periodic work.

        Called once per interval.  Must not swallow :class:`asyncio.CancelledError`.
        """

    async def _run_loop(self) -> None:
        """Main scheduling loop — runs until the stop event is set."""
        if self.initial_delay_seconds > 0:
            await self._interruptible_sleep(self.initial_delay_seconds)
            if self._stop_event.is_set():
                return

        backoff_multiplier: float = 1.0

        while not self._stop_event.is_set():
            try:
                await self.run_cycle()
                backoff_multiplier = 1.0  # reset on success
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.exception(
                    "worker_cycle_error",
                    worker=type(self).__name__,
                    error=str(exc),
                    policy=str(self.on_error_policy),
                )
                if self.on_error_policy is OnErrorPolicy.STOP:
                    return
                if self.on_error_policy is OnErrorPolicy.BACKOFF:
                    backoff_multiplier = min(backoff_multiplier * 2.0, 10.0)

            if self._stop_event.is_set():
                break

            sleep = self.interval_seconds * backoff_multiplier
            if self.max_jitter_seconds > 0:
                sleep += random.uniform(0, self.max_jitter_seconds)  # noqa: S311
            await self._interruptible_sleep(sleep)

    async def _interruptible_sleep(self, seconds: float) -> None:
        """Sleep for *seconds*, waking early if the stop event fires."""
        try:
            await asyncio.wait_for(self._stop_event.wait(), timeout=seconds)
        except TimeoutError:
            pass


__all__ = ["MonitorScheduledWorker"]
