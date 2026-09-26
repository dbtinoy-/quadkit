"""Context-propagation utilities for async tasks and thread pools.

These helpers ensure ``contextvars`` values survive boundary crossings
(new tasks, thread-pool offloads).  They do **not** depend on any
global state.
"""

from __future__ import annotations

import asyncio
import contextvars
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

T = TypeVar("T")


def create_task_with_context(
    coro: Coroutine[Any, Any, T],
    *,
    name: str | None = None,
) -> asyncio.Task[T]:
    """Create an ``asyncio.Task`` with the current context propagated.

    In Python 3.11+ ``asyncio.create_task`` already copies context
    automatically.  This wrapper exists for clarity and documentation.
    """
    return asyncio.create_task(coro, name=name)


def run_in_threadpool_with_context(
    func: Callable[..., T],
    *args: Any,
    **kwargs: Any,
) -> asyncio.Future[T]:
    """Run a synchronous callable in the default thread-pool executor
    with the current ``contextvars`` context snapshot propagated.

    Uses ``get_running_loop()`` (not the deprecated
    ``get_event_loop()``).
    """
    ctx = contextvars.copy_context()
    loop = asyncio.get_running_loop()
    return loop.run_in_executor(
        None,
        lambda: ctx.run(func, *args, **kwargs),
    )


__all__ = [
    "create_task_with_context",
    "run_in_threadpool_with_context",
]
