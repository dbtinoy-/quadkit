"""Performance Monitor — async operation metrics collection."""

from __future__ import annotations

import asyncio
from collections import deque
import contextlib
from contextlib import asynccontextmanager
import cProfile
import io
import os
import pstats
import time
import tracemalloc
from typing import TYPE_CHECKING, Any

from quadkit.concurrency.task_utils import create_tracked_task
from quadkit.monitor.profiling.models import (
    FunctionProfileResult,
    PerformanceMetrics,
    PerformanceMonitorConfig,
    PerformanceMonitorError,
    PerformanceSnapshot,
)
from quadkit.monitor.types import PerformanceMonitorState

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


class PerformanceMonitor:
    """Async performance monitor with periodic CPU/memory sampling.

    Collects snapshots at ``config.sampling_interval`` intervals while active.
    Use :meth:`start_monitoring` / :meth:`stop_monitoring` or the async
    :meth:`monitor_context` context manager to bracket monitored regions.
    """

    def __init__(self, config: PerformanceMonitorConfig | None = None) -> None:
        """Initialise monitor with optional configuration.

        Args:
            config: Performance monitoring configuration (defaults apply).
        """
        self._config = config or PerformanceMonitorConfig()
        self._state: PerformanceMonitorState = PerformanceMonitorState.STOPPED
        self._metrics: PerformanceMetrics = PerformanceMetrics()
        self._background_tasks: set[asyncio.Task[Any]] = set()

    @property
    def state(self) -> PerformanceMonitorState:
        """Return the current monitoring state."""
        return self._state

    @property
    def metrics(self) -> PerformanceMetrics:
        """Return the accumulated performance metrics."""
        return self._metrics

    async def start_monitoring(self) -> None:
        """Start periodic metrics collection.

        Raises:
            PerformanceMonitorError: If monitoring is already active.
        """
        if self._state == PerformanceMonitorState.MONITORING:
            raise PerformanceMonitorError("Cannot start monitoring — already active")

        self._metrics = PerformanceMetrics(
            start_time=time.monotonic(),
            snapshots=deque(maxlen=self._config.max_metrics_history),
        )
        self._state = PerformanceMonitorState.MONITORING

        if self._config.enable_memory_tracking:
            tracemalloc.start()

        create_tracked_task(
            self._sampling_loop(),
            self._background_tasks,
            name="profiling_collect_sampling",
        )

    async def stop_monitoring(self) -> None:
        """Stop metrics collection and finalise metrics."""
        if self._state != PerformanceMonitorState.MONITORING:
            return

        self._state = PerformanceMonitorState.STOPPED

        # Cancel all background tasks
        for task in self._background_tasks:
            task.cancel()

        # Wait for cancellation
        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)
            self._background_tasks.clear()

        with contextlib.suppress(Exception):
            tracemalloc.stop()

        self._metrics.end_time = time.monotonic()
        self._aggregate_metrics()

    @asynccontextmanager
    async def monitor_context(self) -> AsyncGenerator[PerformanceMonitor, None]:
        """Async context manager that starts and stops monitoring automatically.

        Yields:
            This monitor instance.
        """
        await self.start_monitoring()
        try:
            yield self
        finally:
            await self.stop_monitoring()

    async def profile_function(
        self, func: Any, *args: Any, **kwargs: Any
    ) -> FunctionProfileResult:
        """Profile a synchronous or asynchronous function.

        Args:
            func: Callable to profile (sync or async).
            *args: Positional arguments for *func*.
            **kwargs: Keyword arguments for *func*.

        Returns:
            :class:`FunctionProfileResult` with timing and memory data.
        """
        if self._config.enable_memory_tracking:
            if not tracemalloc.is_tracing():
                tracemalloc.start()
            tracemalloc.clear_traces()

        profiler = cProfile.Profile()
        memory_before = self._get_memory_usage()
        start_wall = time.monotonic()
        start_cpu = time.process_time()

        try:
            profiler.enable()
            if asyncio.iscoroutinefunction(func):
                await func(*args, **kwargs)
            else:
                func(*args, **kwargs)
        finally:
            profiler.disable()

        elapsed_wall = time.monotonic() - start_wall
        elapsed_cpu = time.process_time() - start_cpu
        memory_after = self._get_memory_usage()
        memory_delta = max(0, memory_after - memory_before)

        # Capture cProfile stats as a string
        stream = io.StringIO()
        ps = pstats.Stats(profiler, stream=stream)
        ps.sort_stats(self._config.profile_sort_by)
        ps.print_stats(self._config.profile_max_lines)
        profile_stats = stream.getvalue()

        return FunctionProfileResult(
            function_name=getattr(func, "__name__", repr(func)),
            execution_time=elapsed_wall,
            cpu_time=elapsed_cpu,
            memory_delta=memory_delta,
            profile_stats=profile_stats,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _sampling_loop(self) -> None:
        """Background loop — collects a snapshot every sampling_interval."""
        while self._state == PerformanceMonitorState.MONITORING:
            with contextlib.suppress(Exception):
                snapshot = self._collect_snapshot()
                self._metrics.snapshots.append(snapshot)
                self._metrics.total_samples += 1
            await asyncio.sleep(self._config.sampling_interval)

    def _collect_snapshot(self) -> PerformanceSnapshot:
        """Collect a single performance snapshot."""
        cpu_percent = 0.0
        with contextlib.suppress(Exception):
            import psutil  # type: ignore[import-untyped]

            cpu_percent = psutil.cpu_percent(interval=None)

        memory_usage = self._get_memory_usage()

        all_tasks = asyncio.all_tasks()
        active = len([t for t in all_tasks if not t.done()])

        return PerformanceSnapshot(
            timestamp=time.monotonic(),
            cpu_percent=cpu_percent,
            memory_usage=memory_usage,
            memory_peak=memory_usage,
            active_tasks=active,
            pending_tasks=max(0, active - 1),  # exclude sampling task
            total_tasks=len(all_tasks),
        )

    def _get_memory_usage(self) -> int:
        """Return current memory usage in bytes."""
        if self._config.enable_memory_tracking and tracemalloc.is_tracing():
            current, _ = tracemalloc.get_traced_memory()
            return current

        with contextlib.suppress(Exception):
            import psutil

            proc = psutil.Process(os.getpid())
            rss_memory: int = proc.memory_info().rss
            return rss_memory
        return 0

    def _aggregate_metrics(self) -> None:
        """Calculate aggregate statistics from collected snapshots."""
        if not self._metrics.snapshots:
            return

        snapshots = self._metrics.snapshots
        self._metrics.average_cpu_percent = sum(s.cpu_percent for s in snapshots) / len(
            snapshots
        )
        self._metrics.average_memory_usage = int(
            sum(s.memory_usage for s in snapshots) / len(snapshots)
        )
        self._metrics.peak_memory_usage = max(s.memory_peak for s in snapshots)
        self._metrics.max_active_tasks = max(s.active_tasks for s in snapshots)


__all__ = ["PerformanceMonitor"]
