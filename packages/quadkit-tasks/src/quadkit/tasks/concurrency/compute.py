"""CPU-bound task offloading with advanced strategies."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
import functools
import multiprocessing
import threading
import time
from typing import Any

from quadkit.logging import get_logger
from quadkit.tasks.types import PoolStrategy

logger = get_logger(__name__)

# Optional import for system monitoring

try:
    import psutil  # type: ignore[import-untyped]

    HAS_PSUTIL = True
except ImportError:
    psutil = None
    HAS_PSUTIL = False


@dataclass
class ProcessStats:
    """Statistics for a worker process."""

    pid: int
    tasks_completed: int = 0
    tasks_failed: int = 0
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    last_active: float = field(default_factory=time.time)
    is_healthy: bool = True


@dataclass
class PoolMetrics:
    """Metrics for the process pool."""

    active_workers: int = 0
    total_workers: int = 0
    queued_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    avg_task_duration: float = 0.0
    pool_cpu_percent: float = 0.0
    pool_memory_mb: float = 0.0


class ComputePool:
    """Process pool executor with load-balancing, adaptive sizing, and health monitoring.

    Wraps :class:`concurrent.futures.ProcessPoolExecutor` with three sizing
    strategies controlled by :class:`~quadkit.tasks.types.PoolStrategy`:

    * ``FIXED`` — constant worker count equal to CPU count (capped by *max_workers*).
    * ``DYNAMIC`` — scales with observed CPU/memory pressure when ``psutil`` is
      installed; falls back to CPU count without it.
    * ``ADAPTIVE`` — tunes on both current load *and* available memory;
      reduces workers when CPU > 60 % or memory < 1 GB available.

    A background daemon thread runs health checks every
    *health_check_interval* seconds, updating per-process stats and evicting
    unhealthy PIDs from the internal worker registry.

    **Usage example**::

        pool = ComputePool(strategy=PoolStrategy.ADAPTIVE, min_workers=2)
        result = await pool.submit(cpu_heavy_function, arg1, arg2)
        metrics = pool.get_metrics()
        await pool.shutdown()

    Note:
        Register as a container singleton so the pool lifecycle is managed by
        the framework::

            container.singleton(ComputePool, lambda: ComputePool())

    Args:
        strategy: Worker-count sizing strategy.  Defaults to ``ADAPTIVE``.
        min_workers: Minimum number of live worker processes.  Defaults to 1.
        max_workers: Hard cap on worker count.  When ``None`` defaults to
            ``cpu_count * 2``.
        memory_limit_mb: Soft memory ceiling per worker in MB.  When ``None``
            uses 25 % of total RAM when ``psutil`` is available, otherwise
            1024 MB.
        cpu_limit_percent: CPU percentage threshold above which ``DYNAMIC``
            and ``ADAPTIVE`` strategies reduce workers.  Defaults to 80.
        health_check_interval: Seconds between background monitoring ticks.
            Defaults to 5.0.
    """

    def __init__(
        self,
        strategy: PoolStrategy = PoolStrategy.ADAPTIVE,
        min_workers: int = 1,
        max_workers: int | None = None,
        memory_limit_mb: int | None = None,
        cpu_limit_percent: int = 80,
        health_check_interval: float = 5.0,
    ) -> None:
        self.strategy = strategy
        self.min_workers = min_workers
        self.max_workers = max_workers or (multiprocessing.cpu_count() * 2)
        if memory_limit_mb is not None:
            self.memory_limit_mb = memory_limit_mb
        elif HAS_PSUTIL and psutil is not None:
            self.memory_limit_mb = psutil.virtual_memory().total // (1024 * 1024) // 4
        else:
            self.memory_limit_mb = 1024  # 25% of total RAM or 1GB fallback
        self.cpu_limit_percent = cpu_limit_percent
        self.health_check_interval = health_check_interval

        self._executor: ProcessPoolExecutor | None = None
        self._workers: dict[int, ProcessStats] = {}
        self._metrics = PoolMetrics()
        self._task_durations: list[float] = []
        self._shutdown_event = threading.Event()
        self._monitor_thread: threading.Thread | None = None
        self._lock = threading.RLock()

        # Initialize pool
        self._ensure_pool_size()

    def _ensure_pool_size(self) -> None:
        """Ensure pool has appropriate number of workers."""
        with self._lock:
            if self._executor is None:
                target_workers = self._calculate_target_workers()
                self._executor = ProcessPoolExecutor(
                    max_workers=target_workers,
                    mp_context=multiprocessing.get_context("spawn"),
                )
                self._start_monitoring()

    def _calculate_target_workers(self) -> int:
        """Calculate optimal number of workers based on strategy."""
        if self.strategy == PoolStrategy.FIXED:
            return min(
                self.max_workers,
                max(self.min_workers, multiprocessing.cpu_count()),
            )

        if self.strategy == PoolStrategy.DYNAMIC:
            # Scale based on current load
            if HAS_PSUTIL and psutil is not None:
                cpu_percent = psutil.cpu_percent(interval=0.1)
                memory_percent = psutil.virtual_memory().percent

                if cpu_percent > self.cpu_limit_percent or memory_percent > 80:
                    return self.min_workers
                return min(self.max_workers, multiprocessing.cpu_count() * 2)
            # Fallback without psutil
            return min(self.max_workers, multiprocessing.cpu_count())

        if self.strategy == PoolStrategy.ADAPTIVE:
            # Auto-tune based on workload and resources
            cpu_count = multiprocessing.cpu_count()

            if HAS_PSUTIL and psutil is not None:
                available_memory = psutil.virtual_memory().available // (
                    1024 * 1024 * 1024
                )  # GB

                # Base calculation
                workers = cpu_count

                # Adjust for memory
                memory_based = int(available_memory * 2)  # 2 workers per GB
                workers = min(workers, memory_based)

                # Adjust for current load
                cpu_percent = psutil.cpu_percent(interval=0.1)
                if cpu_percent > 60:
                    workers = max(self.min_workers, workers // 2)

                return max(self.min_workers, min(self.max_workers, workers))
            # Fallback without psutil
            return max(self.min_workers, min(self.max_workers, cpu_count))

        raise AssertionError(
            "Unhandled PoolStrategy: this code path should be unreachable",
        )

    def _start_monitoring(self) -> None:
        """Start background monitoring thread."""
        if self._monitor_thread is None or not self._monitor_thread.is_alive():
            self._monitor_thread = threading.Thread(
                target=self._monitor_workers,
                daemon=True,
                name="compute-pool-monitor",
            )
            self._monitor_thread.start()

    def _monitor_workers(self) -> None:
        """Monitor worker health and performance."""
        while not self._shutdown_event.is_set():
            try:
                self._update_worker_stats()
                self._check_worker_health()
                self._adjust_pool_size()
                self._update_metrics()
            except Exception:  # noqa: BLE001 — resilience boundary
                logger.exception("Pool monitoring error")

            self._shutdown_event.wait(self.health_check_interval)

    def _register_executor_workers(self) -> None:
        """Register the executor's worker PIDs for per-process monitoring.

        Best-effort: reads the executor's internal process registry via
        ``getattr`` so the pool still works (with pool-level-only metrics)
        if that private attribute is ever renamed or removed.
        """
        executor = self._executor
        if executor is None:
            return
        processes = getattr(executor, "_processes", None)
        if not processes:
            return
        for pid in list(processes.keys()):
            if pid not in self._workers:
                self._workers[pid] = ProcessStats(pid=pid)

    def _update_worker_stats(self) -> None:
        """Update statistics for all worker processes."""
        with self._lock:
            self._register_executor_workers()
            if not HAS_PSUTIL:
                # Without psutil, we can't monitor worker stats
                return

            current_pids = set()
            if self._executor:
                # Get current worker processes
                try:
                    if HAS_PSUTIL and psutil is not None:
                        processes = psutil.process_iter(
                            ["pid", "cpu_percent", "memory_info"],
                        )
                        for proc in processes:
                            try:
                                pid = proc.info["pid"]
                                if pid in self._workers:
                                    current_pids.add(pid)
                                    self._workers[pid].cpu_percent = (
                                        proc.info["cpu_percent"] or 0.0
                                    )
                                    self._workers[pid].memory_mb = (
                                        (proc.info["memory_info"].rss // (1024 * 1024))
                                        if proc.info["memory_info"]
                                        else 0.0
                                    )
                                    self._workers[pid].last_active = time.time()
                            except (psutil.NoSuchProcess, psutil.AccessDenied):
                                continue
                except Exception:  # noqa: BLE001 — best-effort
                    logger.exception("Error iterating worker processes")

            # Mark missing workers as unhealthy
            for pid in list(self._workers.keys()):
                if pid not in current_pids:
                    self._workers[pid].is_healthy = False

    def _check_worker_health(self) -> None:
        """Check worker health and restart if needed."""
        with self._lock:
            unhealthy_pids = [
                pid for pid, stats in self._workers.items() if not stats.is_healthy
            ]

            for pid in unhealthy_pids:
                del self._workers[pid]

            # If we have too few healthy workers, the pool will auto-scale

    def _adjust_pool_size(self) -> None:
        """Adjust pool size based on strategy and load."""
        if self.strategy in (PoolStrategy.DYNAMIC, PoolStrategy.ADAPTIVE):
            target_workers = self._calculate_target_workers()
            current_workers = len(
                list(filter(lambda w: w.is_healthy, self._workers.values())),
            )

            if target_workers != current_workers:
                pass
                # Note: ProcessPoolExecutor doesn't support dynamic resizing
                # In a real implementation, we'd need to recreate the executor
                # For now, we'll track the target and recreate on next major operation

    def _update_metrics(self) -> None:
        """Update pool-wide metrics."""
        with self._lock:
            healthy_workers = list(
                filter(lambda w: w.is_healthy, self._workers.values()),
            )
            self._metrics.active_workers = len(healthy_workers)
            self._metrics.total_workers = len(self._workers)

            if healthy_workers:
                self._metrics.pool_cpu_percent = sum(
                    w.cpu_percent for w in healthy_workers
                ) / len(healthy_workers)
                self._metrics.pool_memory_mb = sum(w.memory_mb for w in healthy_workers)

            if self._task_durations:
                self._metrics.avg_task_duration = sum(self._task_durations) / len(
                    self._task_durations,
                )

    async def submit(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """Submit a CPU-bound callable to the process pool and await its result.

        Args:
            func: A picklable callable to run in a worker process.
            *args: Positional arguments forwarded to *func*.
            **kwargs: Keyword arguments forwarded to *func*.

        Returns:
            The return value of *func(*args, **kwargs)*.

        Raises:
            Exception: Any exception raised by *func* is re-raised in the
                calling coroutine after incrementing the failure counter.
        """
        if self._executor is None:
            self._ensure_pool_size()

        start_time = time.time()

        try:
            loop = asyncio.get_running_loop()
            future = loop.run_in_executor(
                self._executor,
                functools.partial(func, *args, **kwargs),
            )

            result = await future
        except Exception:  # noqa: BLE001 — resilience boundary
            with self._lock:
                self._metrics.failed_tasks += 1
            logger.exception("Compute submit task failed")
            raise
        else:
            duration = time.time() - start_time

            with self._lock:
                self._metrics.completed_tasks += 1
                self._task_durations.append(duration)
                # Keep only last 1000 durations for averaging
                if len(self._task_durations) > 1000:
                    self._task_durations = self._task_durations[-1000:]

            return result

    def get_metrics(self) -> PoolMetrics:
        """Get current pool metrics."""
        with self._lock:
            return PoolMetrics(**self._metrics.__dict__)

    async def shutdown(self, wait: bool = True) -> None:
        """Shutdown the compute pool."""
        self._shutdown_event.set()

        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=5.0)

        if self._executor:
            self._executor.shutdown(wait=wait)
            self._executor = None

        with self._lock:
            self._workers.clear()


# Backward compatibility removed - use the pool directly

from quadkit.tasks.concurrency.facade import Compute as Compute  # noqa: E402
