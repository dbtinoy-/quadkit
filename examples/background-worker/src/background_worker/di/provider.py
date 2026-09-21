"""Convention followed: **Provider lifecycle** — ``register()`` declares
singletons (including the controller, as a class binding), ``boot()``
starts the engine and rebinds the wired controller, ``shutdown()``
drains the pool, ``health_check()`` reports readiness;
``config_key``/``config_model`` wire the typed yaml section into
``self.config``.

Lifecycle wiring for the Background Worker demo: the worker loop starts
in ``boot()`` and drains in ``shutdown()`` — the same phases you would
use to connect to a real broker later.
"""

from __future__ import annotations

from background_worker.config import BackgroundWorkerConfig
from background_worker.controllers.api import WorkController
from background_worker.services.worker import TaskQueue, WorkerEngine
from quadkit.contracts.core import HealthCheckResult, HealthStatus
from quadkit.contracts.core.di import (
    ContainerRegistrarProtocol,
    ContainerResolverProtocol,
)
from quadkit.di.provider import Provider


class BackgroundWorkerProvider(Provider):
    """Own the queue and the engine lifecycle."""

    name = "background_worker"
    config_key: str | None = "background_worker"
    config_model: type | None = BackgroundWorkerConfig

    def __init__(self) -> None:
        super().__init__()
        self._engine: WorkerEngine | None = None

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        config = (
            self.config
            if isinstance(self.config, BackgroundWorkerConfig)
            else BackgroundWorkerConfig()
        )
        container.singleton(BackgroundWorkerConfig, config)
        container.singleton(TaskQueue, instance=TaskQueue())
        container.singleton(WorkController, WorkController)

    async def boot(self, container: ContainerResolverProtocol) -> None:
        config = await container.resolve(BackgroundWorkerConfig)
        queue = await container.resolve(TaskQueue)
        engine = WorkerEngine(
            queue, concurrency=config.concurrency, poll_timeout=config.poll_timeout
        )
        engine.start()
        self._engine = engine
        container.bind(WorkController, WorkController(queue))

    async def shutdown(self) -> None:
        if self._engine is not None:
            await self._engine.stop()
            self._engine = None

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Report provider wiring for framework health aggregation."""
        return HealthCheckResult(
            component=self.name,
            status=HealthStatus.HEALTHY
            if self._engine is not None
            else HealthStatus.UNHEALTHY,
            details={
                "demo": "background-worker",
                "engine_running": self._engine is not None,
            },
        )


__all__ = ["BackgroundWorkerProvider"]
