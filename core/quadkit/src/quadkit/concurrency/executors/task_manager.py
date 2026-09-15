"""Task management with priority and lifecycle support."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from quadkit.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from quadkit.logging import LoggerProtocol


class TaskManager:
    """Manages async tasks with critical/background distinction.

    Critical tasks are awaited during shutdown with a generous timeout.
    Background tasks are cancelled immediately during shutdown.

    Usage::

        tm = get_task_manager()
        tm.create_critical_task(my_coro(), name="important-work")
        tm.create_background_task(cleanup_coro())
    """

    def __init__(self) -> None:
        self._critical: set[asyncio.Task[Any]] = set()
        self._background: set[asyncio.Task[Any]] = set()
        self._task_counter: int = 0
        self._logger: LoggerProtocol = get_logger(__name__)

    # -- Task creation -----------------------------------------------------

    def create_critical_task(
        self,
        coro: Coroutine[Any, Any, Any],
        name: str | None = None,
    ) -> asyncio.Task[Any]:
        """Create a task that will be awaited during shutdown.

        Args:
            coro: The coroutine to run.
            name: Optional task name for debugging.

        Returns:
            The created asyncio.Task.
        """
        return self._create_task(coro, name=name, critical=True)

    def create_background_task(
        self,
        coro: Coroutine[Any, Any, Any],
        name: str | None = None,
    ) -> asyncio.Task[Any]:
        """Create a task that will be cancelled during shutdown.

        Args:
            coro: The coroutine to run.
            name: Optional task name for debugging.

        Returns:
            The created asyncio.Task.
        """
        return self._create_task(coro, name=name, critical=False)

    def run_periodic(
        self,
        coro_func: Callable[[], Coroutine[Any, Any, Any]],
        interval: float,
        name: str | None = None,
        critical: bool = False,
    ) -> asyncio.Task[Any]:
        """Run a coroutine periodically at a fixed interval.

        Args:
            coro_func: Function that returns a coroutine to run.
            interval: Interval between runs in seconds.
            name: Optional task name.
            critical: Whether the periodic task is critical.

        Returns:
            The task managing the periodic execution.
        """

        async def _periodic_wrapper() -> None:
            while True:
                start_time = asyncio.get_event_loop().time()
                try:
                    await coro_func()
                except BaseException as exc:
                    if isinstance(
                        exc, (asyncio.CancelledError, KeyboardInterrupt, SystemExit)
                    ):
                        raise
                    if isinstance(exc, Exception):
                        self._logger.exception(
                            "task_manager.periodic_task_error",
                            task=name or "unnamed",
                            error=str(exc),
                        )
                        continue
                    raise

                elapsed = asyncio.get_event_loop().time() - start_time
                sleep_time = max(0, interval - elapsed)
                await asyncio.sleep(sleep_time)

        return self._create_task(_periodic_wrapper(), name=name, critical=critical)

    # -- Shutdown ----------------------------------------------------------

    async def shutdown_gracefully(
        self,
        critical_timeout: float = 10.0,
        background_timeout: float = 2.0,
    ) -> None:
        """Gracefully shut down all managed tasks.

        Phase 1: Wait for critical tasks up to ``critical_timeout``.
        Phase 2: Cancel background tasks and wait up to ``background_timeout``.

        Args:
            critical_timeout: Max seconds to wait for critical tasks.
            background_timeout: Max seconds to wait for background cancellation.
        """
        self._logger.info(
            "task_manager.shutting_down",
            critical=len(self._critical),
            background=len(self._background),
        )

        # Phase 1: Wait for critical tasks
        if self._critical:
            critical_tasks = list(self._critical)
            _done, pending = await asyncio.wait(
                critical_tasks,
                timeout=critical_timeout,
                return_when=asyncio.ALL_COMPLETED,
            )
            if pending:
                self._logger.warning(
                    "task_manager.critical_timeout",
                    timed_out=len(pending),
                    timeout=critical_timeout,
                )
                for task in pending:
                    self._logger.warning(
                        "task_manager.critical_incomplete",
                        task=task.get_name(),
                    )

        # Phase 2: Cancel background tasks
        if self._background:
            background_tasks = list(self._background)
            for task in background_tasks:
                if not task.done():
                    task.cancel()

            if background_tasks:
                await asyncio.wait(
                    background_tasks,
                    timeout=background_timeout,
                    return_when=asyncio.ALL_COMPLETED,
                )

        self._logger.info("task_manager.shutdown_complete")

    # -- Query -------------------------------------------------------------

    def get_task(self, name: str) -> asyncio.Task[Any] | None:
        """Get a task by name, or None if not found or already completed."""
        for task in self._critical:
            if task.get_name() == name:
                return task
        for task in self._background:
            if task.get_name() == name:
                return task
        return None

    def get_task_counts(self) -> dict[str, int]:
        """Get the count of active critical and background tasks."""
        return {
            "critical": len(self._critical),
            "background": len(self._background),
        }

    @property
    def has_active_tasks(self) -> bool:
        """Check if any tasks are still running."""
        return bool(self._critical or self._background)

    # -- Internal ----------------------------------------------------------

    def _create_task(
        self,
        coro: Coroutine[Any, Any, Any],
        *,
        name: str | None = None,
        critical: bool = True,
    ) -> asyncio.Task[Any]:
        """Internal task creation."""
        task_name = name or self._generate_name(
            "critical" if critical else "background",
        )
        task = asyncio.create_task(coro, name=task_name)
        target_set = self._critical if critical else self._background
        target_set.add(task)
        task.add_done_callback(target_set.discard)
        self._logger.debug(
            "task.created",
            name=task_name,
            priority="critical" if critical else "background",
        )
        return task

    def _generate_name(self, prefix: str) -> str:
        self._task_counter += 1
        return f"{prefix}-{self._task_counter}"


__all__ = ["TaskManager"]
