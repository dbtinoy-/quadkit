"""Convention followed: **Provider pattern** — ``register()`` declares
singletons, ``boot()`` resolves contracts, ``health_check()`` reports
readiness.

Lifecycle wiring for the Task Console showcase.

``TasksModule.configure()`` is a global module: it exports
``TaskExecutorProtocol``/``TaskQueueProtocol`` and additionally registers
``TaskProviderProtocol``, ``ResultStore``, and ``WorkerPool`` as global
singletons (visible everywhere because the module is global, not because
they're in its ``exports`` list — the same pattern this demo relies on).
This provider resolves those, registers the demo's own handlers through the
real ``register_handler``/``register_scheduled_task`` API, and builds the
browser-facing ``TaskConsoleService`` on top.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from quadkit.contracts.core import HealthCheckResult, HealthStatus
from quadkit.contracts.infra.tasks import TaskProviderProtocol
from quadkit.di.provider import Provider
from quadkit.tasks.decorators import scheduled
from quadkit.tasks.dlq.core import DeadLetterQueue
from quadkit.tasks.execution.pool import WorkerPool
from quadkit.tasks.results.core import ResultStore
from task_console.config import TaskConsoleConfig
from task_console.controllers.api import TaskConsoleApiController
from task_console.services import handlers as demo_handlers

if TYPE_CHECKING:
    from quadkit.contracts.core.di import (
        ContainerRegistrarProtocol,
        ContainerResolverProtocol,
    )


@scheduled("*/1 * * * *", name="scheduled_heartbeat")
async def _scheduled_heartbeat() -> dict[str, object]:
    """A real ``@scheduled`` job: the demo's TaskScheduler enqueues this every minute."""
    return await demo_handlers.flaky_ping(jitter=True)


class TaskConsoleProvider(Provider):
    """Resolve the package-owned task stack and wire the browser service.

    ``TasksModule.configure()`` does all the real work (worker pool,
    scheduler, result store, DLQ); this provider only registers the demo's
    own handlers against the real ``TaskProviderProtocol.register_handler``
    and ``register_scheduled_task`` entry points and exposes a small
    console over them.
    """

    name = "task_console"
    config_key: str | None = "task_console"
    config_model: type | None = TaskConsoleConfig

    def __init__(self) -> None:
        super().__init__()
        self._service: object | None = None

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        """Bind the demo config singleton.

        Args:
            container: DI registrar received from the framework.
        """
        config = (
            self.config
            if isinstance(self.config, TaskConsoleConfig)
            else TaskConsoleConfig()
        )
        container.singleton(TaskConsoleConfig, config)

    async def boot(self, container: ContainerResolverProtocol) -> None:
        """Register demo handlers, resolve the task stack, and seed sample jobs.

        Args:
            container: DI resolver used to obtain package-owned bindings.
        """
        from task_console.services.console import TaskConsoleService

        config = await container.resolve(TaskConsoleConfig)
        provider = await container.resolve(TaskProviderProtocol)
        result_store = await container.resolve(ResultStore)

        for task_name, handler in demo_handlers.HANDLERS.items():
            provider.register_handler(task_name, handler)
        provider.register_scheduled_task(_scheduled_heartbeat)

        # WorkerPool.get_pool_stats() is exposed through TaskProviderProtocol,
        # but the DLQ each worker routes permanent failures to is a private
        # WorkerPool attribute (quadkit-tasks has no DeadLetterQueue DI
        # binding). We read it the same way audit-trail reads
        # AuditLogger._store — a documented "reach past the exported surface"
        # exception, not a made-up API.
        worker_pool = await container.resolve(WorkerPool)
        dead_letter_queue = getattr(worker_pool, "_dead_letter_queue", None)
        if not isinstance(dead_letter_queue, DeadLetterQueue):
            # Misconfiguration of the demo's own module wiring, not a caller
            # type error: RuntimeError is the right boot-time signal.
            raise RuntimeError(  # noqa: TRY004
                "task-console requires WorkerPool to expose its DeadLetterQueue"
            )

        service = TaskConsoleService(
            provider=provider,
            result_store=result_store,
            dead_letter_queue=dead_letter_queue,
            config=config,
        )
        await service.seed()
        self._service = service

        container.bind(
            TaskConsoleApiController,
            TaskConsoleApiController(service=service),
        )

    async def shutdown(self) -> None:
        """Release the service reference on shutdown."""
        self._service = None

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Delegate health check to the browser-facing service.

        Args:
            timeout: Ignored — the underlying task provider probe is fast.

        Returns:
            :class:`~quadkit.contracts.core.HealthCheckResult`.
        """
        if self._service is None:
            return HealthCheckResult(
                component="task_console",
                status=HealthStatus.DEGRADED,
                message="service not booted",
            )
        result = await self._service.health()
        return HealthCheckResult(
            component="task_console",
            status=HealthStatus(result["status"]),
            details=result["details"],
        )


__all__ = ["TaskConsoleProvider"]
