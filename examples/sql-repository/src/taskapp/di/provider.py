"""Convention followed: **Provider pattern** — ``register()`` declares singletons, ``boot()`` resolves contracts, ``health_check()`` reports readiness.

Lifecycle wiring for the SQL-backed task repository demo."""

from __future__ import annotations

from typing import TYPE_CHECKING

from quadkit.contracts.core.health import (
    HealthCheckCategory,
    HealthCheckResult,
    HealthStatus,
)
from quadkit.contracts.data import DatabaseProviderProtocol
from quadkit.di.provider import Provider
from taskapp.config import TaskAppConfig
from taskapp.controllers.api import TasksApiController
from taskapp.repository.fixtures import SEED_TASKS
from taskapp.repository.tasks import TaskRepository

if TYPE_CHECKING:
    from quadkit.contracts.core.di import (
        ContainerRegistrarProtocol,
        ContainerResolverProtocol,
    )

__all__ = ["TaskProvider"]


class TaskProvider(Provider):
    """Bind one repository-backed task resource through DI lifecycle hooks."""

    name = "task_app"
    config_key: str | None = "task_app"
    config_model: type | None = TaskAppConfig

    def __init__(self) -> None:
        super().__init__()
        self._database: DatabaseProviderProtocol | None = None

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        """Declare config and controller keys before cross-module resolution."""
        cfg = self.config or TaskAppConfig()
        container.singleton(TaskAppConfig, instance=cfg)
        container.singleton(TasksApiController, TasksApiController)

    async def boot(self, container: ContainerResolverProtocol) -> None:
        """Resolve DatabaseProviderProtocol, migrate the table, and seed rows."""
        database = await container.resolve(DatabaseProviderProtocol)
        repository = TaskRepository(database)
        await repository.initialize(SEED_TASKS)
        self._database = database
        container.bind(TasksApiController, TasksApiController(repository=repository))

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Delegate readiness to the Quadkit database provider when available."""
        if self._database is None:
            return HealthCheckResult(
                component=self.name,
                status=HealthStatus.UNHEALTHY,
                category=HealthCheckCategory.READINESS,
            )
        return await self._database.health_check(timeout=timeout)
