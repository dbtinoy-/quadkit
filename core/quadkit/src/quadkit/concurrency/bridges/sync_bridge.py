"""Bridge for executing async code from sync contexts."""

from __future__ import annotations

import asyncio
import concurrent.futures
import inspect
from typing import TYPE_CHECKING, Any, TypeVar, cast

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

T = TypeVar("T")


class SyncBridge:
    """Standardized bridge for running async code from sync environments.

    Handles the complexities of nested loops and thread pool execution.
    """

    @staticmethod
    def run(
        coro: Awaitable[T] | Callable[..., Awaitable[T]],
        *args: Any,
        executor: concurrent.futures.Executor | None = None,  # noqa: ARG004
        **kwargs: Any,
    ) -> T:
        """Run async code synchronously.

        Accepts either an awaitable or an async callable + arguments.  The
        work is delegated to helper methods to reduce complexity and make the
        behaviour easier to test and reason about.
        """
        actual_coro: Awaitable[T]
        if inspect.iscoroutine(coro):
            actual_coro = coro
        elif callable(coro):
            actual_coro = coro(*args, **kwargs)
        else:
            raise TypeError(f"Expected coroutine or async function, got {type(coro)}")

        return cast("T", SyncBridge._run_coro(actual_coro))

    @staticmethod
    def _run_coro(coro: Awaitable[T]) -> T:
        """Execute an awaitable in the current thread, handling running loops.

        This encapsulates the previous logic of checking for an existing
        event loop, offloading via ``asyncio.run`` or a thread pool when
        necessary. Separating it allows clearer unit testing and avoids the
        large monolithic ``run`` method.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # No loop in this thread, safe to use asyncio.run
            return asyncio.run(coro)  # type: ignore[arg-type]

        if loop.is_running():
            # Already running, must offload to a thread.  This is common in
            # web servers or when called from within another task.
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:

                def _run_in_new_loop(c: Awaitable[T]) -> T:
                    return asyncio.run(c)  # type: ignore[arg-type]

                future = pool.submit(_run_in_new_loop, coro)
                return future.result()

        # Loop exists but not running (uncommon)
        return loop.run_until_complete(coro)

    @staticmethod
    def call_sync(
        func: Callable[..., Awaitable[T] | T],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """Call a function synchronously, handle async conversion if needed.

        Raises RuntimeError if called from within an async context to prevent
        blocking the event loop. Use 'await .call()' or 'await .execute()' instead.
        """
        if SyncBridge._is_async_context():
            raise RuntimeError(
                f"{func.__name__}() cannot be called synchronously from inside "
                f"an async context. Use 'await {func.__name__}()' instead.",
            )
        if not SyncBridge.is_async(func) and not inspect.iscoroutine(func):
            return cast("T", func(*args, **kwargs))
        return SyncBridge.run(func, *args, **kwargs)  # type: ignore[arg-type]

    @staticmethod
    def _is_async_context() -> bool:
        """Check if we're running inside an async event loop.

        Returns True if there's a running event loop - this means call_sync()
        would block the loop if we run sync code.
        """
        try:
            loop = asyncio.get_running_loop()
            return loop.is_running()
        except RuntimeError:
            return False

    @staticmethod
    def is_async(func: Any) -> bool:
        """Check if a function is async."""
        return inspect.iscoroutinefunction(func) or inspect.isasyncgenfunction(func)
