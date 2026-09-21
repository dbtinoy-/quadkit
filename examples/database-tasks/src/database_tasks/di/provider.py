"""Convention followed: **Provider lifecycle** — ``register()`` declares
singletons (including the controller, as a class binding), ``boot()``
opens the resource and rebinds the wired controller, ``shutdown()``
closes the resource, ``health_check()`` reports readiness;
``config_key``/``config_model`` wire the typed yaml section into
``self.config``.

Lifecycle wiring for the Database Tasks demo: the SQLite repository is a
DI singleton, so tests and handlers share one connection factory, and
the connection is closed on shutdown instead of leaking.
"""

from __future__ import annotations

from database_tasks.config import DatabaseTasksConfig
from database_tasks.controllers.api import TasksController
from database_tasks.services.repository import TaskRepository
from quadkit.contracts.core import HealthCheckResult, HealthStatus
from quadkit.contracts.core.di import (
    ContainerRegistrarProtocol,
    ContainerResolverProtocol,
)
from quadkit.di.provider import Provider


class DatabaseTasksProvider(Provider):
    """Own the repository lifecycle and the controller wiring."""

    name = "database_tasks"
    config_key: str | None = "database_tasks"
    config_model: type | None = DatabaseTasksConfig

    def __init__(self) -> None:
        super().__init__()
        self._repo: TaskRepository | None = None

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        config = (
            self.config
            if isinstance(self.config, DatabaseTasksConfig)
            else DatabaseTasksConfig()
        )
        container.singleton(DatabaseTasksConfig, config)
        container.singleton(TasksController, TasksController)

    async def boot(self, container: ContainerResolverProtocol) -> None:
        config = await container.resolve(DatabaseTasksConfig)
        repo = TaskRepository(config.db_path)  # fail fast if the path is bad
        self._repo = repo
        container.bind(TasksController, TasksController(repo))

    async def shutdown(self) -> None:
        if self._repo is not None:
            self._repo.close()
            self._repo = None

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Report whether the database answers a trivial query."""
        healthy = self._repo is not None and self._repo.health()
        return HealthCheckResult(
            component=self.name,
            status=HealthStatus.HEALTHY if healthy else HealthStatus.UNHEALTHY,
            details={"demo": "database-tasks", "database_reachable": healthy},
        )


__all__ = ["DatabaseTasksProvider"]
