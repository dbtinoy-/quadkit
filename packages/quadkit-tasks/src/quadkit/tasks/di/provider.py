"""Task provider for Quadkit Framework integration."""

from __future__ import annotations

import asyncio
from typing import Any

from quadkit.contracts.core import ProviderPriority
from quadkit.contracts.infra.tasks import TaskQueueProtocol
from quadkit.di.provider import Provider
from quadkit.tasks.backends.registry import TaskBackendRegistry
from quadkit.tasks.config import TaskConfig
from quadkit.tasks.di._lifecycle import (  # noqa: F401 — re-export
    _check_queue_health,
    _connect_queue,
    _TaskLifecycleMixin,
    _wire_queue_hooks,
)
from quadkit.tasks.di._operations import _TaskOperationsMixin
from quadkit.tasks.di._registration import _TaskRegistrationMixin
from quadkit.tasks.execution.pool import WorkerPool
from quadkit.tasks.execution.registry import HandlerRegistry
from quadkit.tasks.middleware.core import TaskMiddlewarePipeline
from quadkit.tasks.results.core import InMemoryResultStore, ResultStore


class TaskProvider(
    _TaskLifecycleMixin,
    _TaskOperationsMixin,
    _TaskRegistrationMixin,
    Provider,
):
    """Task processing provider for Quadkit Framework.

    TaskProvider integrates task processing with the framework, providing
    dependency injection, lifecycle management, scheduling, and worker-pool
    orchestration.
    """

    name = "tasks"
    priority = ProviderPriority.INFRASTRUCTURE
    config_key: str | None = "tasks"
    config_model: type | None = TaskConfig

    def __init__(
        self,
        queue: TaskQueueProtocol,
        worker_count: int = 1,
        enable_scheduler: bool = True,
        middleware_pipeline: TaskMiddlewarePipeline | None = None,
        config: TaskConfig | None = None,
        task_modules: list[str] | tuple[str, ...] | None = None,
        task_packages: list[str] | tuple[str, ...] | None = None,
    ) -> None:
        """Initialize the task provider.

        Args:
            queue: Task queue implementation to use.
            worker_count: Number of workers to create.
            enable_scheduler: Whether to enable cron scheduling.
            middleware_pipeline: Optional middleware pipeline applied to every
                worker in the pool.
            config: Optional typed tasks configuration. When ``None``, the
                orchestrator may late-inject the ``tasks`` yaml section before
                :meth:`register`.
            task_modules: Exact Python module paths to import during boot and
                scan for ``@task`` / ``@scheduled`` callables.
            task_packages: Package roots to import recursively during boot and
                scan for decorated task callables.
        """
        super().__init__()
        self.queue = queue
        self.worker_count = worker_count
        self.enable_scheduler = enable_scheduler
        self._middleware_pipeline = middleware_pipeline
        self._task_modules = tuple(task_modules or ())
        self._task_packages = tuple(task_packages or ())

        self.worker_pool: WorkerPool | None = None
        self.scheduler = None
        self.scheduler_task: asyncio.Task[Any] | None = None

        self._result_store: ResultStore = InMemoryResultStore()
        self.registry = HandlerRegistry()
        self._backend_registry = TaskBackendRegistry.with_defaults()
        self._config: TaskConfig | None = config
        self._queue_services: list[tuple[str, Any]] = []
        self._background_tasks: set[asyncio.Task[Any]] = set()

    @classmethod
    def from_config(cls, config: TaskConfig, **context: Any) -> TaskProvider:
        """Create a TaskProvider from a TaskConfig.

        Context kwargs may include a pre-built ``queue`` plus optional
        ``task_modules`` / ``task_packages`` discovery roots. If no queue is
        provided, a :class:`~quadkit.tasks.backends.memory.MemoryTaskQueue`
        is created.
        """
        from quadkit.tasks.backends.memory import MemoryTaskQueue

        queue = context.get("queue") or MemoryTaskQueue()  # type: ignore[abstract]
        provider = cls(
            queue=queue,
            worker_count=(getattr(config.worker, "worker_count", None) or 1),
            enable_scheduler=getattr(
                getattr(config, "scheduler", None), "enabled", True
            ),
            task_modules=context.get("task_modules"),
            task_packages=context.get("task_packages"),
        )
        provider._config = config
        return provider


__all__ = ["TaskProvider"]
