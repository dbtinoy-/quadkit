"""Smart Dispatcher for async/sync execution."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import contextvars
import functools
import inspect
from typing import TYPE_CHECKING, Any, TypeVar, cast

from quadkit.concurrency.config import DispatcherConfig
from quadkit.concurrency.exceptions import DispatcherError

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

T = TypeVar("T")


class DispatcherImpl:
    """Executes sync and async functions with automatic detection.

    Sync functions are offloaded to a thread pool with context
    propagation. Async functions run directly on the event loop.

    ## Config vs Per-Call Parameters

    ### Config (set at initialization):
    - ``max_workers``: Maximum threads in the pool
    - ``pool_type``: ThreadPool or ProcessPool
    - ``default_timeout``: Default timeout for all calls

    ### Per-Call Parameters (set at call time):
    - ``executor``: Override the default thread pool
    - ``timeout``: Override the default timeout for this specific call

    Usage::

        # Using config (applies to all calls)
        config = DispatcherConfig(max_workers=10, default_timeout=30.0)
        dispatcher = DispatcherImpl(config)

        # Using per-call params (overrides config for this call)
        result = await dispatcher.run(sync_function, timeout=60.0)
        result = await dispatcher.run(sync_function, executor=custom_pool)
    """

    def __init__(self, config: DispatcherConfig | None = None) -> None:
        self._config = config or DispatcherConfig()
        self._cpu_pool: ThreadPoolExecutor | None = None
        self._io_pool: ThreadPoolExecutor | None = None
        self._draining: bool = False
        self._active_count: int = 0
        self._active_lock: asyncio.Lock = asyncio.Lock()

    # -- Execution ---------------------------------------------------------

    async def run(
        self,
        func: Callable[..., T],
        *args: Any,
        executor: ThreadPoolExecutor | None = None,
        timeout: float | None = None,
        **kwargs: Any,
    ) -> T:
        """Execute a function, automatically choosing sync or async path."""
        if self._draining:
            raise RuntimeError("Dispatcher is draining; no new tasks accepted")

        async with self._active_lock:
            self._active_count += 1
        try:
            if _is_async(func):
                return await self._run(func, args, kwargs, timeout)
            return await self._run_sync(func, args, kwargs, executor, timeout)
        finally:
            async with self._active_lock:
                self._active_count -= 1

    async def _run(
        self,
        func: Callable[..., T],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        timeout: float | None,
    ) -> T:
        """Run an async function on the event loop."""
        coro = func(*args, **kwargs)
        if timeout is not None:
            return await asyncio.wait_for(coro, timeout=timeout)  # type: ignore[arg-type]
        return await cast("Awaitable[T]", coro)

    async def _run_sync(
        self,
        func: Callable[..., T],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        executor: ThreadPoolExecutor | None,
        timeout: float | None,
    ) -> T:
        """Run a sync function in a thread pool with context propagation."""
        self._ensure_pools()
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.get_event_loop()

        pool = executor or self._io_pool
        ctx = contextvars.copy_context()

        coro = loop.run_in_executor(
            pool,
            ctx.run,
            functools.partial(func, *args, **kwargs),
        )

        if timeout is not None:
            return await asyncio.wait_for(coro, timeout=timeout)
        return await coro

    async def run_many(
        self,
        tasks: list[tuple[Callable[..., Any], tuple[Any, ...], dict[str, Any]]],
        concurrency: int | None = None,
        timeout: float | None = None,
    ) -> list[Any]:
        """Execute multiple functions concurrently.

        Args:
            tasks: List of ``(func, args, kwargs)`` tuples.
            concurrency: Max concurrent executions. None = unlimited.
            timeout: Per-task timeout.

        Returns:
            Results in the same order as tasks.
        """
        semaphore = asyncio.Semaphore(concurrency) if concurrency else None

        async def _execute(func: Callable, args: tuple, kwargs: dict) -> Any:
            if semaphore:
                async with semaphore:
                    return await self.run(func, *args, timeout=timeout, **kwargs)
            return await self.run(func, *args, timeout=timeout, **kwargs)

        return await asyncio.gather(*[_execute(fn, a, kw) for fn, a, kw in tasks])

    # -- Pool management ---------------------------------------------------

    def _ensure_pools(self) -> None:
        """Initialize thread pools if not yet created."""
        import os

        cpu_count = os.cpu_count() or 1
        if self._cpu_pool is None:
            cpu_cfg = self._config.get_cpu_pool_config()
            self._cpu_pool = ThreadPoolExecutor(
                max_workers=cpu_cfg.get_max_workers(default=cpu_count),
                thread_name_prefix=cpu_cfg.thread_name_prefix
                or "quadkit-dispatcher-cpu",
            )

        if self._io_pool is None:
            io_cfg = self._config.get_io_pool_config()
            self._io_pool = ThreadPoolExecutor(
                max_workers=io_cfg.get_max_workers(default=cpu_count * 4),
                thread_name_prefix=io_cfg.thread_name_prefix or "quadkit-dispatcher-io",
            )

    @property
    def cpu_pool(self) -> ThreadPoolExecutor:
        """Get the CPU-bound executor, initializing if needed."""
        self._ensure_pools()
        assert self._cpu_pool is not None  # noqa: S101  # _ensure_pools constructs it
        return self._cpu_pool

    @property
    def io_pool(self) -> ThreadPoolExecutor:
        """Get the I/O-bound executor, initializing if needed."""
        self._ensure_pools()
        assert self._io_pool is not None  # noqa: S101  # _ensure_pools constructs it
        return self._io_pool

    # -- Lifecycle ---------------------------------------------------------

    async def shutdown(
        self,
        wait: bool = True,
        drain: bool = False,
        drain_timeout: float | None = None,
    ) -> None:
        """Shutdown the dispatcher and release thread pools."""
        if drain:
            self._draining = True
            if self._active_count > 0 and drain_timeout:
                import time

                deadline = time.monotonic() + drain_timeout
                while self._active_count > 0 and time.monotonic() < deadline:
                    await asyncio.sleep(0.05)

        if self._cpu_pool is not None:
            self._cpu_pool.shutdown(wait=wait)
            self._cpu_pool = None

        if self._io_pool is not None:
            self._io_pool.shutdown(wait=wait)
            self._io_pool = None

        self._draining = False

    @property
    def is_draining(self) -> bool:
        """Check if dispatcher is rejecting new tasks."""
        return self._draining

    @property
    def active_task_count(self) -> int:
        """Number of currently executing tasks."""
        return self._active_count


# -- Utilities -------------------------------------------------------------


def _is_async(func: Callable) -> bool:
    """Check if a callable is async."""
    return inspect.iscoroutinefunction(func) or inspect.isasyncgenfunction(func)


async def dispatch(
    func: Callable[..., T],
    *args: Any,
    dispatcher: DispatcherImpl | None = None,
    **kwargs: Any,
) -> T:
    """Run a function via the provided dispatcher.

    Thin convenience wrapper around ``DispatcherImpl.run()``.  The
    dispatcher **must** be supplied explicitly.

    Args:
        func: The function to run.
        args: Positional arguments forwarded to *func*.
        dispatcher: DispatcherImpl instance to use (required).
        kwargs: Keyword arguments forwarded to *func*.

    Raises:
        DispatcherError: If *dispatcher* is ``None``.

    Example::

        from quadkit.concurrency.executors.dispatcher import DispatcherImpl, dispatch
        dispatcher = DispatcherImpl()
        result = await dispatch(my_function, "arg1", dispatcher=dispatcher)
    """
    if dispatcher is None:
        raise DispatcherError(
            "No dispatcher provided. "
            "Dispatcher must be passed explicitly to dispatch().",
        )
    return await dispatcher.run(func, *args, **kwargs)


async def shutdown_dispatcher(
    dispatcher: DispatcherImpl | None = None,
    **kwargs: Any,
) -> None:
    """Shutdown the provided dispatcher.

    No-op when *dispatcher* is ``None`` (graceful teardown).

    Args:
        dispatcher: DispatcherImpl instance to shutdown.
    """
    if dispatcher is None:
        return
    await dispatcher.shutdown(**kwargs)


def run_sync(
    func: Callable[..., Any],
    *args: Any,
    **kwargs: Any,
) -> Any:
    """Run an async function or coroutine synchronously.

    Bridges async code into synchronous contexts by delegating to
    :class:`~quadkit.concurrency.sync_bridge.SyncBridge`.  If *func*
    is already synchronous (and not a coroutine), it is called directly
    without overhead.

    This is intended for **CLI scripts, tests, and bootstrap code** where
    no event loop is running yet.  Do not call this from within an
    already-running async context — it will deadlock.

    Args:
        func: An async or sync callable.
        args: Positional arguments forwarded to *func*.
        kwargs: Keyword arguments forwarded to *func*.

    Returns:
        The return value of *func*.

    Example::

        async def fetch_data() -> dict:
            ...

        data = run_sync(fetch_data)
    """
    from quadkit.concurrency.bridges.sync_bridge import SyncBridge

    if not SyncBridge.is_async(func) and not inspect.iscoroutine(func):
        return func(*args, **kwargs)

    return SyncBridge.run(func, *args, **kwargs)


__all__ = [
    "DispatcherError",
    "DispatcherImpl",
    "dispatch",
    "run_sync",
    "shutdown_dispatcher",
]
