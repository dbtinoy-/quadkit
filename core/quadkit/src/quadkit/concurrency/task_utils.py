# quadkit/src/quadkit/concurrency/task_utils.py
"""Safe background task creation with exception logging.

Every background task in the framework should be created via
``create_tracked_task`` to guarantee exception visibility.
"""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Any, TypeVar

from quadkit.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


def _handle_task_exception(task: asyncio.Task[Any]) -> None:
    """Log exception from a completed task.

    Registered as a ``done_callback``; inspects ``task.exception()``
    so exceptions from background tasks are never silently discarded.
    """
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.error(
            "background_task_failed",
            task_name=task.get_name(),
            exc_info=exc,
        )


def create_tracked_task(
    coro: Coroutine[Any, Any, T],
    task_set: set[asyncio.Task[Any]],
    *,
    name: str | None = None,
) -> asyncio.Task[T]:
    """Create an asyncio task that is tracked and logs exceptions.

    Stores the task reference in ``task_set`` to prevent garbage
    collection and registers two callbacks: one to discard the
    reference on completion and one to log any unhandled exception.

    Args:
        coro: The coroutine to schedule.
        task_set: Mutable set owned by the caller for reference tracking.
        name: Optional task name surfaced in logs and ``repr(task)``.

    Returns:
        The scheduled ``asyncio.Task``.
    """
    task: asyncio.Task[T] = asyncio.create_task(coro, name=name)
    task_set.add(task)
    task.add_done_callback(task_set.discard)
    task.add_done_callback(_handle_task_exception)
    return task
