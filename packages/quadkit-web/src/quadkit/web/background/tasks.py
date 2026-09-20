from __future__ import annotations

import asyncio
import contextvars
from typing import TYPE_CHECKING, Any

from quadkit.contracts.web.protocols import BackgroundTaskRunnerProtocol
from quadkit.primitives.context import propagate_context, with_context

if TYPE_CHECKING:
    from collections.abc import Callable


def _is_async_callable(obj: Any) -> bool:
    """Return ``True`` for async functions *and* async callable objects.

    ``asyncio.iscoroutinefunction`` returns ``False`` for instances whose
    class defines ``async def __call__``.  This helper covers both cases so
    that callable objects with an async ``__call__`` are awaited correctly.
    """
    return asyncio.iscoroutinefunction(obj) or asyncio.iscoroutinefunction(
        getattr(type(obj), "__call__", None)
    )


class BackgroundTasks:
    """Accumulates background tasks to run after response is sent.

    Context is captured at :meth:`add` time using :func:`propagate_context`
    so that :meth:`_execute_all` restores the request-scope context variables
    (request_id, trace_id, …) even when called after the original request
    scope has been torn down.
    """

    def __init__(self) -> None:
        self._tasks: list[
            tuple[
                Callable[..., Any], tuple[Any, ...], dict[str, Any], contextvars.Context
            ]
        ] = []

    def add(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        """Add a task to be executed after the response.

        The current :mod:`contextvars` context is snapshotted immediately so
        that :meth:`_execute_all` can restore it at execution time.
        """
        ctx = propagate_context()
        self._tasks.append((func, args, kwargs, ctx))

    async def _execute_all(self) -> None:
        """Execute all queued tasks, each with its captured context restored."""
        for func, args, kwargs, ctx in self._tasks:
            with with_context(ctx):
                if _is_async_callable(func):
                    await func(*args, **kwargs)
                else:
                    func(*args, **kwargs)

    def __len__(self) -> int:
        return len(self._tasks)

    def __bool__(self) -> bool:
        return bool(self._tasks)

    def _to_starlette_task(self) -> Any:
        """Adapt to a Starlette ``BackgroundTask``.

        Internal method for the web routing layer: handlers may return
        ``(payload, BackgroundTasks)`` and the request pipeline attaches the
        adapted task to the outgoing response, so queued work runs after the
        bytes hit the wire with the captured request context restored.
        """
        from starlette.background import BackgroundTask

        return BackgroundTask(self._execute_all)


class StarletteBackgroundTaskRunner(BackgroundTaskRunnerProtocol):
    """Starlette-backed implementation of BackgroundTaskRunnerProtocol.

    Wraps Starlette's BackgroundTasks to provide the framework's
    BackgroundTaskRunnerProtocol without leaking Starlette types
    into the web layer's public API surface.

    Example:
        ```python
        runner = StarletteBackgroundTaskRunner()
        runner.add_task(send_email, to="user@example.com")
        response = JSONResponse(data, background=runner._to_starlette())
        ```
    """

    def __init__(self) -> None:
        from starlette.background import BackgroundTasks as _StarletteBackgroundTasks

        self._starlette_tasks = _StarletteBackgroundTasks()

    def add_task(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        """Add a function to run in the background after the response is sent.

        The current :mod:`contextvars` context is snapshotted immediately so
        that the task sees request-scope variables (request_id, trace_id, …)
        even if the originating request scope has been torn down by the time
        Starlette executes the task.

        Sync callables are wrapped with a sync closure so that Starlette still
        dispatches them to its threadpool via ``run_in_executor``.  Async
        callables (including instances with ``async def __call__``) are wrapped
        with an async closure so they are awaited directly on the event loop.

        Args:
            func: Async or sync callable to execute.
            *args: Positional arguments for the callable.
            **kwargs: Keyword arguments for the callable.
        """
        ctx = propagate_context()

        if _is_async_callable(func):

            async def _async_wrapper(*a: Any, **kw: Any) -> None:
                with with_context(ctx):
                    await func(*a, **kw)

            self._starlette_tasks.add_task(_async_wrapper, *args, **kwargs)
        else:

            def _sync_wrapper(*a: Any, **kw: Any) -> None:
                with with_context(ctx):
                    func(*a, **kw)

            self._starlette_tasks.add_task(_sync_wrapper, *args, **kwargs)

    def _to_starlette(self) -> Any:
        """Return the underlying Starlette BackgroundTasks instance.

        This is an internal method for use by the web routing layer only.
        It must not appear in the public API.
        """
        return self._starlette_tasks


class BackgroundTaskScope:
    """Dependency injection scope for BackgroundTasks.

    The primary, transport-agnostic pattern is returning
    ``(payload, BackgroundTasks)`` from a handler — the request pipeline
    attaches the tasks to the outgoing response. This scope exists for apps
    that prefer wires-through-DI: carry one per request and hand
    ``scope.tasks`` to whichever path drains it.
    """

    def __init__(self) -> None:
        self._tasks = BackgroundTasks()

    @property
    def tasks(self) -> BackgroundTasks:
        return self._tasks

    def add(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        """Add a background task."""
        self._tasks.add(func, *args, **kwargs)


__all__ = [
    "BackgroundTaskScope",
    "BackgroundTasks",
    "StarletteBackgroundTaskRunner",
]
