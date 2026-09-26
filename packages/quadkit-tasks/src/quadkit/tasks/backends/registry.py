"""Task backend registry — maps backend type strings to factory functions.

To register a custom backend::

    from quadkit.tasks.backends.registry import TaskBackendRegistry

    registry = TaskBackendRegistry()
    registry.register("my_backend", lambda cfg: MyTaskQueue(cfg))

    # Inside a Quadkit Application, resolve from the DI container instead:
    registry = await container.resolve(TaskBackendRegistry)
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from quadkit.primitives.registry import BackendRegistry as _CoreBackendRegistry
from quadkit.tasks import constants as tasks_const
from quadkit.tasks.config import TaskConfig

# Type alias for backend factory functions.
BackendFactory = Callable[[TaskConfig], Any]


class TaskBackendRegistry(_CoreBackendRegistry):
    """Registry mapping backend type strings to factory callables.

    Extends :class:`quadkit.primitives.registry.BackendRegistry` so that all
    backend registries share a common hierarchy and introspection API.
    Backends are registered with a string key (``"memory"``, ``"redis"``, …)
    and a factory that accepts a :class:`~quadkit.tasks.config.TaskConfig`
    and returns a ready-to-use queue implementation.
    """

    def __init__(self) -> None:
        """Initialise with an empty registry (populate via with_defaults())."""
        super().__init__(name="tasks.backends", allow_overwrite=True)

    @classmethod
    def _default_entries(cls) -> dict[str, BackendFactory]:
        """Declare the built-in backend factories.

        Returns:
            Mapping of backend type string → factory callable.
        """
        return {
            tasks_const.BACKEND_MEMORY: _create_memory,
            tasks_const.BACKEND_REDIS: _create_redis,
            tasks_const.BACKEND_RABBITMQ: _create_rabbitmq,
            tasks_const.BACKEND_POSTGRES: _create_postgres,
        }

    def register(self, backend_type: str, factory: BackendFactory) -> None:  # type: ignore[override]
        """Register a new backend factory under *backend_type*.

        Overwrites any existing factory for the same *backend_type*.

        Args:
            backend_type: String key used in ``config.backend.type``.
            factory: Callable that accepts a :class:`TaskConfig` and returns a queue.
        """
        super().register(backend_type, factory)

    def available_backends(self) -> list[str]:
        """Return a sorted list of registered backend type strings."""
        return sorted(self.keys())

    def create_backend(self, config: TaskConfig) -> Any:
        """Instantiate a backend for the type declared in *config*.

        Args:
            config: Root task configuration; ``config.backend.type`` selects
                the factory.

        Returns:
            A queue object satisfying
            :class:`~quadkit.contracts.infra.tasks.TaskQueueProtocol`.

        Raises:
            ValueError: If ``config.backend.type`` is not registered.
        """
        backend_type = config.backend.type or tasks_const.DEFAULT_BACKEND
        factory = self.get(backend_type)
        if factory is None:
            raise ValueError(
                f"Unknown task backend: {backend_type!r}. "
                f"Available: {self.available_backends()}"
            )
        return factory(config)


# ---------------------------------------------------------------------------
# Built-in factory functions
# ---------------------------------------------------------------------------


def _create_memory(config: TaskConfig) -> Any:
    """Factory: in-memory task queue (always available; no extras required)."""
    from quadkit.tasks.backends.memory import MemoryTaskQueue

    return MemoryTaskQueue()  # type: ignore[abstract]


def _create_redis(config: TaskConfig) -> Any:
    """Factory: Redis-backed task queue.

    Requires ``pip install quadkit-tasks[redis]``.
    """
    from quadkit.tasks.backends.redis import RedisTaskQueue

    return RedisTaskQueue(  # type: ignore[abstract]
        redis_url=config.backend.redis_url.get_secret_value(),
        queue_name=config.backend.queue_name,
    )


def _create_rabbitmq(config: TaskConfig) -> Any:
    """Factory: RabbitMQ-backed task queue.

    Requires ``pip install quadkit-tasks[rabbitmq]``.
    """
    from quadkit.tasks.backends.rabbitmq import RabbitMQTaskQueue

    return RabbitMQTaskQueue(  # type: ignore[abstract]
        amqp_url=config.backend.amqp_url.get_secret_value(),
        queue_name=config.backend.queue_name,
    )


def _create_postgres(config: TaskConfig) -> Any:
    """Factory: Postgres-backed task queue.

    Requires ``pip install quadkit-tasks[postgres]`` and
    ``config.backend.postgres_dsn`` to be set.
    """
    from quadkit.tasks.backends.postgres import PostgresTaskConfig, PostgresTaskQueue

    if not config.backend.postgres_dsn:
        raise ValueError(
            "config.backend.postgres_dsn must be set when using the 'postgres' backend."
        )
    pg_config = PostgresTaskConfig(dsn=config.backend.postgres_dsn)
    return PostgresTaskQueue(pg_config)
