"""Configuration for the concurrency subsystem.

Consolidates pool, dispatcher, and top-level concurrency configuration
into a single module.  Import order within this file matches dependency
order: pool primitives first, then dispatcher config, then the
top-level :class:`ConcurrencyConfig` that ties everything together.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quadkit.concurrency.constants import (
    DEFAULT_CHANNEL_CAPACITY,
    DEFAULT_DISPATCHER_SHUTDOWN_TIMEOUT,
    DEFAULT_WORKER_THREADS,
)

# ---------------------------------------------------------------------------
# Pool configuration
# ---------------------------------------------------------------------------


@dataclass
class PoolConfig:
    """Configuration for worker pools.

    Attributes:
        min_size: Minimum number of workers (>= 1).
        max_size: Maximum number of workers (>= 1).
        task_queue_size: Size of the task queue (>= 1).
        worker_ttl: Worker time-to-live in seconds (>= 0).
        enable_metrics: Whether to enable metrics collection.
            Reserved: no WorkerPool implementation exists yet (the dispatcher
            uses raw ThreadPoolExecutors); the flag will gate pool metrics
            when worker pools land.
    """

    min_size: int = 1
    max_size: int = 10
    task_queue_size: int = 100
    worker_ttl: float = 3600.0
    enable_metrics: bool = False

    def __post_init__(self) -> None:
        if self.min_size < 1:
            raise ValueError(f"min_size must be >= 1, got {self.min_size}")
        if self.max_size < 1:
            raise ValueError(f"max_size must be >= 1, got {self.max_size}")
        if self.task_queue_size < 1:
            raise ValueError(
                f"task_queue_size must be >= 1, got {self.task_queue_size}"
            )
        if self.worker_ttl < 0:
            raise ValueError(f"worker_ttl must be >= 0, got {self.worker_ttl}")


@dataclass
class ThreadPoolConfig:
    """Configuration for a single ThreadPoolExecutor.

    Attributes:
        max_workers: Maximum number of threads (>= 1, or None for default).
        thread_name_prefix: Prefix for thread names. None means caller-supplied default.
    """

    max_workers: int | None = None
    thread_name_prefix: str | None = None

    def __post_init__(self) -> None:
        if self.max_workers is not None and self.max_workers < 1:
            raise ValueError(
                f"max_workers must be >= 1 when set, got {self.max_workers}"
            )

    def get_max_workers(self, default: int | None = None) -> int | None:
        """Return configured max workers, falling back to *default*.

        Args:
            default: Value to return when max_workers is not explicitly set.

        Returns:
            Resolved maximum worker count.
        """
        return self.max_workers if self.max_workers is not None else default


# ---------------------------------------------------------------------------
# Dispatcher configuration
# ---------------------------------------------------------------------------


@dataclass
class DispatcherConfig:
    """Configuration for task dispatchers.

    Attributes:
        max_concurrent_tasks: Maximum number of concurrent tasks (>= 1).
        queue_timeout: Queue timeout in seconds (>= 0).
        pool: Worker pool configuration.
        cpu_pool: CPU-bound thread pool configuration.
        io_pool: I/O-bound thread pool configuration.
    """

    max_concurrent_tasks: int = 100
    queue_timeout: float = 30.0
    pool: PoolConfig = field(default_factory=PoolConfig)
    cpu_pool: ThreadPoolConfig = field(default_factory=ThreadPoolConfig)
    io_pool: ThreadPoolConfig = field(default_factory=ThreadPoolConfig)

    def __post_init__(self) -> None:
        if self.max_concurrent_tasks < 1:
            raise ValueError(
                f"max_concurrent_tasks must be >= 1, got {self.max_concurrent_tasks}"
            )
        if self.queue_timeout < 0:
            raise ValueError(f"queue_timeout must be >= 0, got {self.queue_timeout}")

    def get_cpu_pool_config(self) -> ThreadPoolConfig:
        """Return the CPU-bound thread pool configuration.

        Returns:
            ThreadPoolConfig for the CPU-bound executor.
        """
        return self.cpu_pool

    def get_io_pool_config(self) -> ThreadPoolConfig:
        """Return the I/O-bound thread pool configuration.

        Returns:
            ThreadPoolConfig for the I/O-bound executor.
        """
        return self.io_pool


# ---------------------------------------------------------------------------
# Top-level concurrency configuration
# ---------------------------------------------------------------------------


@dataclass
class ConcurrencyConfig:
    """Async concurrency primitives and task management configuration."""

    default_channel_capacity: int = DEFAULT_CHANNEL_CAPACITY
    # consumed by: ConcurrencyProvider.boot() -> BoundedChannel.configure();
    #   channels created without an explicit capacity pick this up (explicit
    #   ``capacity=0`` still means unbounded).
    worker_threads: int = DEFAULT_WORKER_THREADS
    # consumed by: thread pool executor in ConcurrencyProvider.register()
    dispatcher_shutdown_timeout: float = DEFAULT_DISPATCHER_SHUTDOWN_TIMEOUT
    # consumed by: ConcurrencyProvider.shutdown() -> Dispatcher.shutdown(
    #   drain=True, drain_timeout=...)


__all__ = [
    "ConcurrencyConfig",
    "DispatcherConfig",
    "PoolConfig",
    "ThreadPoolConfig",
]
