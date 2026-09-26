"""Boot, shutdown, and health-check methods."""

from __future__ import annotations

import asyncio
import contextlib
import time
from typing import TYPE_CHECKING, Any

from quadkit.concurrency.task_utils import create_tracked_task
from quadkit.contracts.core import (
    HealthCheckResult,
    HealthStatus,
    HookRegistryProtocol,
)
from quadkit.contracts.core.health import HealthCheckCategory
from quadkit.contracts.observability.metrics import (
    HealthCheckRegistryProtocol as _HealthCheckRegistry,
)
from quadkit.logging import get_logger
from quadkit.tasks.admin.contributor import TasksAdminContributor
from quadkit.tasks.di._attrs import _TaskAttrsMixin
from quadkit.tasks.di._discovery import discover_registered_tasks
from quadkit.tasks.execution.health import TaskHealth
from quadkit.tasks.execution.pool import WorkerPool
from quadkit.tasks.results.cache_backend import CacheBackendResultStore
from quadkit.tasks.scheduling.scheduler import TaskScheduler

if TYPE_CHECKING:
    from quadkit.contracts.core.di import (
        ContainerResolverProtocol,
    )

logger = get_logger(__name__)


class _TaskLifecycleMixin(_TaskAttrsMixin):
    """See TaskProvider."""

    if TYPE_CHECKING:

        def register_scheduled_task(self, task_func: Any) -> None: ...
        def register_handler(self, task_name: str, handler: Any) -> None: ...

    async def boot(self, container: ContainerResolverProtocol) -> None:
        """Start the task provider.

        Called by the framework on application startup after all registrations.
        """
        from quadkit.logging import LoggerProtocol as Logger

        # Resolve logger from container if available
        logger_instance = logger
        with contextlib.suppress(Exception):
            resolved = await container.resolve_optional(Logger)
            if resolved is not None:
                logger_instance = resolved

        self.logger = logger_instance.bind(provider="tasks")
        self.logger.info("Starting TaskProvider...")

        # Boot admin contributor
        contributor = await container.resolve(TasksAdminContributor)
        if contributor is not None:
            await contributor.on_admin_boot(container)

        hooks = await container.resolve_optional(HookRegistryProtocol)
        _wire_queue_hooks(self.queue, hooks)
        for _, queue in self._queue_services:
            _wire_queue_hooks(queue, hooks)

        # Multi-backend: connect all named queues in parallel before the rest of
        # the boot sequence.  Workers/scheduler always use self.queue (the primary).
        if self._queue_services:
            results = await asyncio.gather(
                *(_connect_queue(name, queue) for name, queue in self._queue_services),
                return_exceptions=True,
            )
            errors = [r for r in results if isinstance(r, BaseException)]
            if errors:
                # Roll back: close any queues that connected successfully.
                for _, queue in reversed(self._queue_services):
                    if hasattr(queue, "close"):
                        try:
                            await queue.close()
                        except Exception:  # noqa: BLE001, S110
                            pass
                raise errors[0]
            self.logger.info(
                "tasks_named_queues_connected",
                count=len(self._queue_services),
            )

        # Upgrade to CacheBackendResultStore if a CacheBackendProtocol is available.
        with contextlib.suppress(Exception):
            from quadkit.contracts.infra.cache import (
                CacheBackendProtocol as _CacheBackend,
            )

            cache_backend = await container.resolve(_CacheBackend)
            if cache_backend is not None:
                self._result_store = CacheBackendResultStore(cache_backend)
                self.logger.info(
                    "TaskProvider: using CacheBackendResultStore for distributed result persistence"
                )

        # Create the scheduler before task autodiscovery so scheduled handlers
        # can register their cron expressions during boot.
        if self.enable_scheduler:
            self.scheduler = TaskScheduler()

        discovered_tasks = discover_registered_tasks(
            task_modules=self._task_modules,
            task_packages=self._task_packages,
        )
        for task_func in discovered_tasks:
            cron = getattr(task_func, "_cron", None)
            if cron is not None:
                self.register_scheduled_task(task_func)
                continue

            task_name = getattr(task_func, "_task_name", None)
            if task_name is None:
                continue
            self.register_handler(task_name, task_func)

        # Initialize worker pool with the shared registry so later refreshes
        # can propagate runtime registrations into existing workers.
        self.worker_pool = WorkerPool(
            self.queue,
            self.registry,
            self.worker_count,
            logger=self.logger,
            hooks=hooks,
            container=container,
            middleware_pipeline=self._middleware_pipeline,
        )
        await self.worker_pool.start()
        # Warn when running an in-memory queue outside of development/testing.
        from quadkit.tasks.backends.memory import MemoryTaskQueue

        if isinstance(self.queue, MemoryTaskQueue):
            env = "development"
            with contextlib.suppress(Exception):
                from quadkit.contracts.core.config import ConfigProtocol

                config = await container.resolve_optional(ConfigProtocol)
                if config is not None:
                    # Config object typically has .environment which is an Enum
                    env = getattr(config.environment, "value", str(config.environment))

            if env not in ("development", "test", "testing"):
                self.logger.warning(
                    "tasks_memory_queue_in_production",
                    note=(
                        "MemoryTaskQueue is volatile — all enqueued tasks will be lost "
                        "on process restart. Use RedisTaskQueue or RabbitMQTaskQueue "
                        "in production deployments."
                    ),
                    env=env,
                )

        if self.enable_scheduler and self.scheduler is not None:
            self.scheduler_task = create_tracked_task(
                self.scheduler.start_scheduler(self._enqueue_job),
                self._background_tasks,
                name="task_provider_scheduler",
            )

        self.logger.info(
            "TaskProvider started with %d workers (%d autodiscovered tasks)",
            self.worker_count,
            len(discovered_tasks),
        )

        # Register task health check with the kernel's HealthChecker if available.
        # This is a best-effort registration; a missing HealthChecker just means
        # health information is not surfaced through the kernel's aggregated endpoint.
        with contextlib.suppress(Exception):
            health_checker = await container.resolve(_HealthCheckRegistry)
            health_checker.add(
                "tasks",
                self.health_check,
                category=HealthCheckCategory.READINESS,
            )
            self.logger.debug("Registered task health check with kernel HealthChecker")

    async def shutdown(self) -> None:
        """Shutdown the task provider gracefully"""
        if hasattr(self, "logger"):
            self.logger.info("Shutting down TaskProvider...")
        else:
            logger.info("Shutting down TaskProvider...")

        # Stop scheduler
        if self.scheduler_task:
            if self.scheduler:
                await self.scheduler.stop_scheduler()
            self.scheduler_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.scheduler_task

        # Stop worker pool
        if self.worker_pool:
            await self.worker_pool.stop()

        # Close named queues LIFO (multi-backend mode).
        if self._queue_services:
            for _, queue in reversed(self._queue_services):
                if hasattr(queue, "close"):
                    try:
                        await queue.close()
                    except Exception:  # noqa: BLE001, S110
                        pass

        # Close primary queue (always — single-backend and multi-backend both use it
        # for workers/scheduler).
        await self.queue.close()

        if hasattr(self, "logger"):
            self.logger.info("TaskProvider shutdown complete")
        else:
            logger.info("TaskProvider shutdown complete")

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Check task provider health.

        In multi-backend mode the overall status is the worst individual status
        across all named queues.  ``TaskQueueProtocol`` does not expose a
        ``health_check()`` method, so liveness is probed via ``get_task_count()``.

        Returns:
            HealthCheckResult with current status and metrics.
        """
        if self._queue_services:
            results = await asyncio.gather(
                *(_check_queue_health(queue) for _, queue in self._queue_services),
                return_exceptions=True,
            )
            worst = HealthStatus.HEALTHY
            for r in results:
                if isinstance(r, BaseException) or r.status == HealthStatus.UNHEALTHY:
                    worst = HealthStatus.UNHEALTHY
                elif (
                    r.status == HealthStatus.DEGRADED
                    and worst != HealthStatus.UNHEALTHY
                ):
                    worst = HealthStatus.DEGRADED
            return HealthCheckResult(
                component=self.name,
                status=worst,
                duration_ms=0.0,
                category=HealthCheckCategory.READINESS,
            )

        # ------------------------------------------------------------------ #
        # Single-backend path (original behaviour, preserved exactly)         #
        # ------------------------------------------------------------------ #
        try:
            queue_size = await self.queue.get_task_count()

            health_data = TaskHealth(
                status="healthy",
                message="Task provider is operational",
                timestamp=time.time(),
                queue_size=queue_size,
                worker_count=self.worker_count,
                scheduler_enabled=self.enable_scheduler,
            )

            # Add worker pool stats if available
            if self.worker_pool:
                pool_stats = self.worker_pool.get_pool_stats()
                health_data.active_workers = pool_stats["active_workers"]
                health_data.total_jobs_processed = pool_stats["total_jobs_processed"]
                health_data.total_jobs_succeeded = pool_stats["total_jobs_succeeded"]
                health_data.total_jobs_failed = pool_stats["total_jobs_failed"]
                health_data.details["pool_stats"] = pool_stats

            return HealthCheckResult(
                component=self.name,
                status=HealthStatus.HEALTHY,
                details=health_data.to_dict(),
                category=HealthCheckCategory.READINESS,
            )

        except Exception as e:
            # Intentionally broad: health checks should report failure rather than raising.
            logger.exception("TaskProvider health check failed")
            health_data = TaskHealth(status="unhealthy", message=str(e))
            return HealthCheckResult(
                component=self.name,
                status=HealthStatus.UNHEALTHY,
                error=str(e),
                details=health_data.to_dict(),
                category=HealthCheckCategory.READINESS,
            )


async def _connect_queue(name: str, queue: Any) -> None:  # noqa: RUF029
    """Connect a single named queue if it exposes a ``connect()`` method."""
    if hasattr(queue, "connect"):
        await queue.connect()


def _wire_queue_hooks(queue: Any, hooks: HookRegistryProtocol | None) -> None:
    """Attach an optional hook registry to a queue when supported."""
    if hasattr(queue, "set_hook_registry"):
        queue.set_hook_registry(hooks)


async def _check_queue_health(queue: Any) -> HealthCheckResult:
    """Probe a queue by calling ``get_task_count()`` (cheapest round-trip).

    ``TaskQueueProtocol`` does not define a ``health_check()`` method so we
    use ``get_task_count()`` as the liveness indicator.
    """
    try:
        await queue.get_task_count()
        return HealthCheckResult(component="tasks", status=HealthStatus.HEALTHY)
    except Exception as exc:  # noqa: BLE001
        return HealthCheckResult(
            component="tasks",
            status=HealthStatus.UNHEALTHY,
            error=str(exc),
        )
