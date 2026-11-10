"""Tests for single-backend TaskConfig wiring and producer/worker role configuration."""

from __future__ import annotations

import pytest

from quadkit.contracts.infra.tasks import TaskQueueProtocol
from quadkit.di import Container
from quadkit.tasks import TasksModule
from quadkit.tasks.backends.memory import MemoryTaskQueue
from quadkit.tasks.backends.redis import RedisTaskQueue
from quadkit.tasks.config import (
    TaskBackendConfig,
    TaskConfig,
    TaskSchedulerConfig,
    TaskWorkerConfig,
)
from quadkit.tasks.di.provider import TaskProvider
from quadkit.validation import SecretStr


@pytest.mark.asyncio
async def test_tasks_module_honors_late_injected_single_backend_config() -> None:
    """Instantiate RedisTaskQueue, worker_count=0, and scheduler=False from YAML config."""
    dyn = TasksModule.configure()
    provider = dyn.providers[0]
    assert isinstance(provider, TaskProvider)

    # Simulate DI orchestrator injecting the ``tasks:`` YAML section before register().
    provider.config = TaskConfig(
        backend=TaskBackendConfig(
            type="redis",
            redis_url=SecretStr("redis://127.0.0.1:6379/2"),
            queue_name="demo-jobs",
        ),
        worker=TaskWorkerConfig(worker_count=0),
        scheduler=TaskSchedulerConfig(enabled=False),
    )

    container = Container()
    await provider.register(container)
    resolved_queue = await container.resolve(TaskQueueProtocol)

    assert isinstance(resolved_queue, RedisTaskQueue)
    assert resolved_queue.redis_url == "redis://127.0.0.1:6379/2"
    assert resolved_queue.queue_name == "demo-jobs"
    assert provider.worker_count == 0
    assert provider.enable_scheduler is False

    await provider.boot(container)
    try:
        assert provider.worker_pool is not None
        assert provider.worker_pool.workers == []
        assert provider.scheduler is None
        assert provider.scheduler_task is None
    finally:
        await provider.shutdown()


@pytest.mark.asyncio
async def test_explicit_tasks_module_arguments_override_config() -> None:
    """Preserve explicit queue, worker_count, and enable_scheduler over TaskConfig."""
    explicit_queue = MemoryTaskQueue()
    cfg = TaskConfig(
        backend=TaskBackendConfig(
            type="redis",
            redis_url=SecretStr("redis://127.0.0.1:6379/3"),
        ),
        worker=TaskWorkerConfig(worker_count=8),
        scheduler=TaskSchedulerConfig(enabled=True),
    )
    dyn = TasksModule.configure(
        queue=explicit_queue,
        worker_count=2,
        enable_scheduler=False,
        config=cfg,
    )
    provider = dyn.providers[0]
    assert isinstance(provider, TaskProvider)
    assert provider._config_from_factory is True  # noqa: SLF001

    container = Container()
    await provider.register(container)
    resolved_queue = await container.resolve(TaskQueueProtocol)

    assert resolved_queue is explicit_queue
    assert provider.worker_count == 2
    assert provider.enable_scheduler is False


def test_from_config_preserves_zero_worker_count() -> None:
    """Keep worker_count=0 intact when constructing TaskProvider.from_config."""
    cfg = TaskConfig(
        worker=TaskWorkerConfig(worker_count=0),
        scheduler=TaskSchedulerConfig(enabled=False),
    )
    provider = TaskProvider.from_config(cfg)
    assert provider.worker_count == 0
    assert provider.enable_scheduler is False
    assert isinstance(provider.queue, MemoryTaskQueue)
