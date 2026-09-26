"""Performance profiling decorators and utility wrappers."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from quadkit.monitor.profiling.models import (
    FunctionProfileResult,
    PerformanceMonitorConfig,
)
from quadkit.monitor.profiling.monitor import PerformanceMonitor

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


@asynccontextmanager
async def monitor_async_operation(
    config: PerformanceMonitorConfig | None = None,
) -> AsyncGenerator[PerformanceMonitor, None]:
    """Async context manager that monitors a region of async code.

    Creates a :class:`PerformanceMonitor`, starts it before entering the body,
    and stops it on exit.

    Args:
        config: Optional :class:`PerformanceMonitorConfig`.  Default config is
            used when not provided.

    Yields:
        Running :class:`PerformanceMonitor` instance.

    Example:
        >>> async with monitor_async_operation() as monitor:
        ...     await do_some_work()
        ... print(monitor.metrics.duration)
    """
    monitor = PerformanceMonitor(config)
    async with monitor.monitor_context() as m:
        yield m


async def profile_async_function(
    func: Any,
    *args: Any,
    **kwargs: Any,
) -> tuple[Any, FunctionProfileResult]:
    """Profile a single async (or sync) function call.

    Args:
        func: Callable to profile.
        *args: Positional arguments forwarded to *func*.
        **kwargs: Keyword arguments forwarded to *func*.

    Returns:
        A ``(result, profile)`` tuple where *result* is the return value of
        *func* and *profile* is a :class:`FunctionProfileResult`.

    Example:
        >>> result, profile = await profile_async_function(my_async_fn, arg1)
        ... print(profile.execution_time)
    """
    import asyncio

    monitor = PerformanceMonitor()

    import cProfile
    import io
    import pstats
    import time

    profiler = cProfile.Profile()
    start_wall = time.monotonic()
    start_cpu = time.process_time()

    try:
        profiler.enable()
        if asyncio.iscoroutinefunction(func):
            result = await func(*args, **kwargs)
        else:
            result = func(*args, **kwargs)
    finally:
        profiler.disable()

    elapsed_wall = time.monotonic() - start_wall
    elapsed_cpu = time.process_time() - start_cpu

    stream = io.StringIO()
    ps = pstats.Stats(profiler, stream=stream)
    ps.sort_stats("cumulative")
    ps.print_stats(50)
    profile_stats = stream.getvalue()

    profile = FunctionProfileResult(
        function_name=getattr(func, "__name__", repr(func)),
        execution_time=elapsed_wall,
        cpu_time=elapsed_cpu,
        memory_delta=0,
        profile_stats=profile_stats,
    )
    _ = monitor  # unused — kept for API compatibility if callers expect monitor config

    return result, profile


__all__ = ["monitor_async_operation", "profile_async_function"]
