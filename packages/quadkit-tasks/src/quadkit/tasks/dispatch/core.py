"""Function-centric background dispatch via ``.delay()``.

Provides the :func:`delay` decorator, which wraps any async function and adds
a ``.delay()`` method for safe fire-and-forget background dispatch.  All
spawned tasks are tracked in a module-level set so CPython's garbage collector
cannot reclaim them before they finish — the canonical prevention for the
"task vanishes" bug (Ruff RUF006).

This is **not** a replacement for the full task-queue system (``@task`` +
``TaskProvider``).  Use ``.delay()`` for lightweight in-process background
work (sending a notification, flushing a local buffer, emitting an audit log)
where queue persistence, retries, and distributed workers are unnecessary.

Example:
    ```python
    from quadkit.tasks.dispatch import delay

    @delay
    async def send_export_email(user_id: str, file_path: str) -> None:
        await mailer.send(user_id, attachment=file_path)

    # Schedules the coroutine as a background asyncio task; returns the Task.
    task = send_export_email.delay(user_id="u-1", file_path="/exports/jan.csv")
    ```

The decorated function remains fully callable as a normal coroutine function:
    ```python
    await send_export_email(user_id="u-1", file_path="/exports/jan.csv")
    ```
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
import functools
from typing import Any, Generic, ParamSpec, TypeVar

_P = ParamSpec("_P")
_R = TypeVar("_R")

# Module-level set that holds references to all live background tasks.
# This prevents CPython from garbage-collecting tasks before they complete
# (asyncio.create_task() only keeps a weak reference internally).
# Tasks remove themselves via the done callback registered in .delay().
_background_tasks: set[asyncio.Task[Any]] = set()


class _DelayedCallable(Generic[_P, _R]):
    """Callable wrapper that adds a ``.delay()`` method to an async function.

    Instances behave identically to the wrapped function when called directly.
    Calling ``.delay()`` instead schedules the coroutine on the running event
    loop and returns the resulting :class:`asyncio.Task`.

    Do not instantiate this class directly — use the :func:`delay` decorator.
    """

    def __init__(self, fn: Callable[_P, Coroutine[Any, Any, _R]]) -> None:
        self._fn = fn
        # Mirror the wrapped function's identity so introspection, logging,
        # and test assertions see the original name / docstring.
        functools.update_wrapper(self, fn)

    def __call__(self, *args: _P.args, **kwargs: _P.kwargs) -> Coroutine[Any, Any, _R]:
        """Call the underlying coroutine function directly.

        Returns a coroutine object; ``await`` it to run synchronously in the
        current task.
        """
        return self._fn(*args, **kwargs)

    def delay(self, *args: _P.args, **kwargs: _P.kwargs) -> asyncio.Task[_R]:
        """Schedule the coroutine as a fire-and-forget background task.

        The task reference is stored in the module-level ``_background_tasks``
        set and automatically removed when the task completes, ensuring the
        coroutine is never garbage-collected before it finishes.

        Args:
            *args: Positional arguments forwarded to the wrapped function.
            **kwargs: Keyword arguments forwarded to the wrapped function.

        Returns:
            The :class:`asyncio.Task` object for the scheduled coroutine.

        Raises:
            RuntimeError: If there is no running event loop (i.e. called
                outside an async context).
        """
        task: asyncio.Task[_R] = asyncio.create_task(
            self._fn(*args, **kwargs),
            name=f"delay:{getattr(self._fn, '__name__', repr(self._fn))}",
        )
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
        return task


def delay(fn: Callable[_P, Coroutine[Any, Any, _R]]) -> _DelayedCallable[_P, _R]:
    """Decorate an async function to add a ``.delay()`` background-dispatch method.

    The decorated function is unchanged when called directly — it still returns
    a coroutine that must be ``await``-ed.  The ``.delay()`` method is the only
    addition; it schedules the coroutine as a background :class:`asyncio.Task`
    and stores the reference to prevent premature garbage collection.

    Args:
        fn: An async function (coroutine function) to wrap.

    Returns:
        A :class:`_DelayedCallable` that is callable exactly like ``fn`` but
        also exposes ``.delay(*args, **kwargs) -> asyncio.Task``.

    Example:
        ```python
        @delay
        async def flush_audit_log(batch: list[AuditEntry]) -> None:
            await audit_store.save_many(batch)

        # Direct call (awaited in the current task):
        await flush_audit_log(batch=entries)

        # Background dispatch (does not block):
        flush_audit_log.delay(batch=entries)
        ```
    """
    return _DelayedCallable(fn)


__all__ = ["delay"]
