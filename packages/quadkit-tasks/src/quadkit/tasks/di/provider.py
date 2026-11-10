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
        queue: TaskQueueProtocol | None = None,
        worker_count: int | None = None,
        enable_scheduler: bool | None = None,
        middleware_pipeline: TaskMiddlewarePipeline | None = None,
        config: TaskConfig | None = None,
        task_modules: list[str] | tuple[str, ...] | None = None,
        task_packages: list[str] | tuple[str, ...] | None = None,
    ) -> None:
        """Initialize the task provider.

        Args:
            queue: Optional explicit task queue implementation. When ``None``,
                the queue is built from ``config.backend`` via
                :class:`TaskBackendRegistry` (falling back to
                :class:`MemoryTaskQueue` when unconfigured).
            worker_count: Optional explicit worker pool size (``0`` disables
                in-process consumption for producer-only processes). Defaults
                to ``config.worker.worker_count`` or ``1``.
            enable_scheduler: Optional explicit scheduler flag. Defaults to
                ``config.scheduler.enabled`` or ``True``.
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
        self._backend_registry = TaskBackendRegistry.with_defaults()
        self._config: TaskConfig | None = config
        self._config_from_factory = config is not None
        self._explicit_queue = queue is not None
        self._explicit_worker_count = worker_count is not None
        self._explicit_enable_scheduler = enable_scheduler is not None

        if queue is not None:
            self.queue = queue
        elif config is not None and not config.backends:
            self.queue = self._backend_registry.create_backend(config)
        else:
            from quadkit.tasks.backends.memory import MemoryTaskQueue

            self.queue = MemoryTaskQueue()

        self.worker_count = (
            worker_count
            if worker_count is not None
            else (config.worker.worker_count if config is not None else 1)
        )
        self.enable_scheduler = (
            enable_scheduler
            if enable_scheduler is not None
            else (config.scheduler.enabled if config is not None else True)
        )
        self._middleware_pipeline = middleware_pipeline
        self._task_modules = tuple(task_modules or ())
        self._task_packages = tuple(task_packages or ())

        self.worker_pool: WorkerPool | None = None
        self.scheduler = None
        self.scheduler_task: asyncio.Task[Any] | None = None

        self._result_store: ResultStore = InMemoryResultStore()
        self.registry = HandlerRegistry()
        self._queue_services: list[tuple[str, Any]] = []
        self._background_tasks: set[asyncio.Task[Any]] = set()

    @classmethod
    def from_config(cls, config: TaskConfig, **context: Any) -> TaskProvider:
        """Create a TaskProvider from a TaskConfig.

        Context kwargs may include a pre-built ``queue`` plus optional
        ``task_modules`` / ``task_packages`` discovery roots. If no queue is
        provided, one is instantiated from ``config.backend`` via
        :class:`TaskBackendRegistry`.
        """
        return cls(
            queue=context.get("queue"),
            config=config,
            task_modules=context.get("task_modules"),
            task_packages=context.get("task_packages"),
        )


__all__ = ["TaskProvider"]
