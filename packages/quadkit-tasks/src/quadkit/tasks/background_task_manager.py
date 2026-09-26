"""BackgroundTaskManager — QK-006.

A container-injectable service for tracking fire-and-go async tasks so that
every background task handle is stored (preventing GC) and so that
``shutdown()`` can cancel them all in an orderly way during framework stop.

Usage::

    class MyService:
        def __init__(self, task_manager: BackgroundTaskManager) -> None:
            self._tasks = task_manager

        async def do_something_in_background(self) -> None:
            self._tasks.track(self._worker())

        async def do_named_work(self) -> None:
            self._tasks.track_named("my-named-job", self._named_worker())

    # In your Provider.shutdown():
    await task_manager.shutdown(timeout=30.0)
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from typing import TypeVar

from quadkit.contracts.infra.tasks import TaskManagerProtocol
from quadkit.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class BackgroundTaskManager(TaskManagerProtocol):
    """Tracks and shuts down background asyncio tasks.

    Implements :class:`~quadkit.contracts.infra.tasks.TaskManagerProtocol`.
    Inject as a ``singleton`` from any DI provider.  Call ``shutdown()``
    during application stop to cancel all in-flight tasks.

    Example::

        manager = BackgroundTaskManager()
        task = manager.track(some_coroutine())
        # … later …
        await manager.shutdown(timeout=30.0)
    """

    def __init__(self) -> None:
        self._tasks: set[asyncio.Task[object]] = set()
        self._names: dict[asyncio.Task[object], str] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def track(self, coro: Awaitable[T]) -> asyncio.Task[T]:
        """Schedule *coro* as an asyncio task and track the handle.

        The task is removed from the tracked set automatically via a
        ``done_callback`` so completed tasks don't accumulate.

        Args:
            coro: Any awaitable to wrap in a task.

        Returns:
            The created :class:`asyncio.Task`.
        """
        task: asyncio.Task[T] = asyncio.create_task(coro)  # type: ignore[arg-type]
        self._register(task, name=None)
        return task

    def track_named(self, name: str, coro: Awaitable[T]) -> asyncio.Task[T]:
        """Like :meth:`track` but attach a human-readable *name* for logs.

        Named tasks appear in ``shutdown()`` timeout warnings so operators
        can identify which work is still running at stop time.

        Args:
            name: Label surfaced in observability/log output.
            coro: Any awaitable to wrap in a task.

        Returns:
            The created :class:`asyncio.Task`.
        """
        task: asyncio.Task[T] = asyncio.create_task(coro, name=name)  # type: ignore[arg-type]
        self._register(task, name=name)
        return task

    @property
    def pending_count(self) -> int:
        """Number of tasks that have not yet completed."""
        return len(self._tasks)

    async def shutdown(self, timeout: float = 30.0) -> None:
        """Cancel all pending tracked tasks and await them.

        After cancellation each task is given up to *timeout* seconds
        collectively to finish (honour CancelledError and finalise any
        ``finally`` blocks).  Tasks that do not stop within the timeout
        are logged by name; no exception is raised.

        Args:
            timeout: Seconds to wait for all tasks to finish after
                cancellation.  Default 30 seconds.
        """
        pending = list(self._tasks)
        if not pending:
            logger.debug("background_task_manager.shutdown_noop")
            return

        logger.info(
            "background_task_manager.shutdown_start",
            pending=len(pending),
        )

        for task in pending:
            if not task.done():
                task.cancel()

        done, still_running = await asyncio.wait(pending, timeout=timeout)

        for task in still_running:
            label = self._names.get(task) or task.get_name()
            logger.warning(
                "background_task_manager.shutdown_timeout",
                task=label,
                timeout=timeout,
            )

        logger.info(
            "background_task_manager.shutdown_complete",
            cancelled=len(done),
            timed_out=len(still_running),
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _register(
        self,
        task: asyncio.Task[object],
        *,
        name: str | None,
    ) -> None:
        """Store task handle and register cleanup/exception callbacks."""
        self._tasks.add(task)
        if name is not None:
            self._names[task] = name

        task.add_done_callback(self._tasks.discard)
        task.add_done_callback(lambda t: self._names.pop(t, None))
        task.add_done_callback(_log_task_exception)


def _log_task_exception(task: asyncio.Task[object]) -> None:
    """Done-callback: log unhandled exceptions from background tasks."""
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.error(
            "background_task_manager.task_failed",
            task_name=task.get_name(),
            exc_info=exc,
        )


__all__ = ["BackgroundTaskManager"]
