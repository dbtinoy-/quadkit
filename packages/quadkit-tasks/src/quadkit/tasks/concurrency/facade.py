"""Global CPU-offloading facade over :class:`ComputePool`."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from quadkit.concurrency.task_utils import create_tracked_task
from quadkit.tasks.types import PoolStrategy

if TYPE_CHECKING:
    from quadkit.tasks.concurrency.compute import ComputePool, PoolMetrics


class Compute:
    """Enhanced CPU-bound task offloading with advanced strategies.

    Supports both global singleton usage and isolated pool instances for testing.
    """

    _pool: ComputePool | None = None
    _is_default_configured: bool = False

    # Hold reference to the shutdown task to avoid GC while shutdown is in progress
    _shutdown_task: asyncio.Task[Any] | None = None

    # Class-level flag to track if we're in test mode
    _test_mode: bool = False
    _original_pool: ComputePool | None = None

    # Track background tasks
    _background_tasks: set[asyncio.Task[Any]] = set()

    @classmethod
    def reset(cls) -> None:
        """Reset Compute state - useful for test isolation.

        This method properly cleans up the pool and resets all class-level state.
        Call this in test fixtures to ensure test isolation.
        """
        if cls._pool is not None:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    cls._shutdown_task = create_tracked_task(
                        cls._pool.shutdown(),
                        cls._background_tasks,
                        name="compute_shutdown_reset",
                    )
                else:
                    loop.run_until_complete(cls._pool.shutdown())
            except Exception:  # noqa: BLE001 — pool shutdown on reset must never raise
                pass
            cls._pool = None

        cls._shutdown_task = None
        cls._is_default_configured = False
        cls._test_mode = False
        cls._original_pool = None

    @classmethod
    def enter_test_mode(cls) -> Compute:
        """Enter test mode with isolated pool.

        Returns a new Compute instance with its own pool.
        Use exit_test_mode() to restore original state.

        Example:
            compute = Compute.enter_test_mode()
            try:
                # use compute...
            finally:
                Compute.exit_test_mode()
        """
        cls._original_pool = cls._pool
        cls._test_mode = True
        cls._pool = None
        cls._is_default_configured = False
        return cls  # type: ignore[return-value]

    @classmethod
    def exit_test_mode(cls) -> None:
        """Exit test mode and restore original pool state."""
        if cls._test_mode:
            if cls._pool is not None:
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        create_tracked_task(
                            cls._pool.shutdown(),
                            cls._background_tasks,
                            name="compute_shutdown_test_exit",
                        )
                    else:
                        loop.run_until_complete(cls._pool.shutdown())
                except Exception:  # noqa: BLE001 — pool shutdown on test-mode exit must never raise
                    pass
            cls._pool = cls._original_pool
            cls._test_mode = False
            cls._original_pool = None

    @classmethod
    def configure(
        cls,
        strategy: PoolStrategy = PoolStrategy.ADAPTIVE,
        min_workers: int = 1,
        max_workers: int | None = None,
        memory_limit_mb: int | None = None,
        cpu_limit_percent: int = 80,
    ) -> None:
        """Configure the compute pool."""
        from quadkit.tasks.concurrency.compute import ComputePool

        if cls._pool:
            # Keep a reference to the shutdown task to avoid it being GC'ed
            try:
                loop = asyncio.get_running_loop()
                cls._shutdown_task = create_tracked_task(
                    cls._pool.shutdown(),
                    cls._background_tasks,
                    name="compute_shutdown_configure",
                )
            except RuntimeError:
                pass  # No running loop — shutdown will be handled synchronously

        cls._pool = ComputePool(
            strategy=strategy,
            min_workers=min_workers,
            max_workers=max_workers,
            memory_limit_mb=memory_limit_mb,
            cpu_limit_percent=cpu_limit_percent,
        )

    @classmethod
    async def run(cls, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """Run a CPU-intensive function with advanced offloading."""
        if cls._pool is None:
            cls.configure()  # Use defaults

        assert cls._pool is not None  # noqa: S101  # configure() guarantees pool
        return await cls._pool.submit(func, *args, **kwargs)

    @classmethod
    def get_metrics(cls) -> PoolMetrics | None:
        """Get current pool metrics."""
        if cls._pool:
            return cls._pool.get_metrics()
        return None

    @classmethod
    async def shutdown(cls) -> None:
        """Shutdown the compute pool."""
        if cls._pool:
            await cls._pool.shutdown()
            cls._pool = None
