"""Shared attribute surface for TaskProvider mixins."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from quadkit.contracts.core.di import ContainerRegistrarProtocol
from quadkit.contracts.core.logging import LoggerProtocol
from quadkit.contracts.infra.tasks.protocols import TaskQueueProtocol
from quadkit.tasks.backends.registry import TaskBackendRegistry
from quadkit.tasks.config import TaskConfig
from quadkit.tasks.execution.pool import WorkerPool
from quadkit.tasks.execution.registry import HandlerRegistry
from quadkit.tasks.middleware.core import TaskMiddlewarePipeline
from quadkit.tasks.results.core import ResultStore
from quadkit.tasks.scheduling.scheduler import TaskScheduler

if TYPE_CHECKING:
    from quadkit.contracts.core.identity import IdGeneratorProtocol
    from quadkit.tasks.models.job import JobProtocol


class _TaskAttrsMixin:
    """Attribute contract shared by all TaskProvider mixins."""

    _backend_registry: TaskBackendRegistry
    _background_tasks: set[asyncio.Task[Any]]
    _config: TaskConfig | None
    _container: ContainerRegistrarProtocol
    _id_generator: IdGeneratorProtocol | None
    _middleware_pipeline: TaskMiddlewarePipeline | None
    _queue_services: list[tuple[str, Any]]
    _result_store: ResultStore
    _task_modules: tuple[str, ...]
    _task_packages: tuple[str, ...]
    enable_scheduler: bool
    logger: LoggerProtocol
    name: str
    queue: TaskQueueProtocol
    registry: HandlerRegistry
    scheduler: TaskScheduler | None
    scheduler_task: asyncio.Task[Any] | None
    worker_count: int
    worker_pool: WorkerPool | None

    if TYPE_CHECKING:

        async def _enqueue_job(self, job: JobProtocol) -> None: ...
