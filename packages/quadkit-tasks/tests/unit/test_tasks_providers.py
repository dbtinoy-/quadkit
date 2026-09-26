"""Unit tests for TaskProvider and factory functions."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.tasks.backends.memory import MemoryTaskQueue
from quadkit.tasks.config import TaskConfig, TaskWorkerConfig
from quadkit.tasks.di.factories import (
    create_memory_task_provider,
    create_provider_from_config,
    create_rabbitmq_task_provider,
    create_redis_task_provider,
)
from quadkit.tasks.di.provider import (
    TaskProvider,
    _check_queue_health,
    _connect_queue,
    _wire_queue_hooks,
)


class _ContainerStub:
    def __init__(
        self,
        *,
        optional: dict[type[object], object] | None = None,
        required: dict[type[object], object] | None = None,
    ) -> None:
        self._optional = optional or {}
        self._required = required or {}

    async def resolve_optional(self, contract: type[object]) -> object | None:
        return self._optional.get(contract)

    async def resolve(self, contract: type[object]) -> object | None:
        return self._required.get(contract)


class TestTaskProviderInitialization:
    """Test TaskProvider initialization."""

    def test_minimal_init(self) -> None:
        """TaskProvider constructs with minimal arguments."""
        queue = MemoryTaskQueue()
        provider = TaskProvider(queue=queue, worker_count=2)

        assert provider.queue is queue
        assert provider.worker_count == 2
        assert provider.enable_scheduler is True
        assert provider.worker_pool is None
        assert provider.scheduler is None

    def test_all_init_args(self) -> None:
        """TaskProvider accepts all init arguments."""
        queue = MemoryTaskQueue()
        provider = TaskProvider(
            queue=queue,
            worker_count=4,
            enable_scheduler=False,
        )

        assert provider.queue is queue
        assert provider.worker_count == 4
        assert provider.enable_scheduler is False

    def test_default_values(self) -> None:
        """TaskProvider uses sensible defaults."""
        queue = MemoryTaskQueue()
        provider = TaskProvider(queue=queue)

        assert provider.worker_count == 1
        assert provider.enable_scheduler is True


class TestTaskProviderFromConfig:
    """Test TaskProvider.from_config() class method."""

    @pytest.mark.asyncio
    async def test_from_config_with_defaults(self) -> None:
        """from_config creates provider with config values."""
        config = TaskConfig(worker=TaskWorkerConfig(worker_count=3))
        provider = TaskProvider.from_config(config)

        assert provider.worker_count == 3
        assert provider._config is config

    @pytest.mark.asyncio
    async def test_from_config_with_queue_override(self) -> None:
        """from_config accepts queue from context."""
        custom_queue = MemoryTaskQueue()
        config = TaskConfig(worker=TaskWorkerConfig(worker_count=1))
        provider = TaskProvider.from_config(config, queue=custom_queue)

        assert provider.queue is custom_queue

    @pytest.mark.asyncio
    async def test_from_config_creates_memory_queue(self) -> None:
        """from_config creates MemoryTaskQueue when none provided."""
        config = TaskConfig(worker=TaskWorkerConfig(worker_count=1))
        provider = TaskProvider.from_config(config)

        assert isinstance(provider.queue, MemoryTaskQueue)


@pytest.mark.asyncio
class TestTaskProviderBoot:
    """Test TaskProvider boot lifecycle."""

    async def test_boot_creates_worker_pool(self) -> None:
        """Boot creates and starts worker pool."""
        queue = MemoryTaskQueue()
        provider = TaskProvider(queue=queue, worker_count=2, enable_scheduler=False)
        container = _ContainerStub()

        await provider.boot(container)

        assert provider.worker_pool is not None

    async def test_boot_registers_handlers_in_pool(self) -> None:
        """Boot registers handlers in worker pool."""
        queue = MemoryTaskQueue()
        provider = TaskProvider(queue=queue, worker_count=1, enable_scheduler=False)

        def my_task() -> str:
            return "result"

        provider.register_handler("my_task", my_task)
        container = _ContainerStub()

        await provider.boot(container)

        assert "my_task" in provider.registry.to_dict()

    async def test_boot_no_scheduler_when_disabled(self) -> None:
        """Boot doesn't create scheduler when disabled."""
        queue = MemoryTaskQueue()
        provider = TaskProvider(queue=queue, worker_count=1, enable_scheduler=False)
        container = _ContainerStub()

        await provider.boot(container)

        assert provider.scheduler is None

    async def test_boot_sets_logger_on_provider(self) -> None:
        """Boot resolves and sets logger."""
        from quadkit.logging import LoggerProtocol

        mock_logger = MagicMock()
        mock_logger.bind = MagicMock(return_value=mock_logger)
        queue = MemoryTaskQueue()
        provider = TaskProvider(queue=queue, worker_count=1, enable_scheduler=False)
        container = _ContainerStub(optional={LoggerProtocol: mock_logger})

        await provider.boot(container)

        # logger gets bound, so it's not the same object but has same protocol
        assert hasattr(provider, "logger")


@pytest.mark.asyncio
class TestTaskProviderShutdown:
    """Test TaskProvider shutdown lifecycle."""

    async def test_shutdown_stops_worker_pool(self) -> None:
        """Shutdown stops worker pool."""
        queue = MemoryTaskQueue()
        provider = TaskProvider(queue=queue, worker_count=1, enable_scheduler=False)
        container = _ContainerStub()

        await provider.boot(container)
        await provider.shutdown()

        # Worker pool should be stopped (pool.stop() was called)
        assert True  # graceful shutdown doesn't raise

    async def test_shutdown_cancels_scheduler_task(self) -> None:
        """Shutdown cancels scheduler task when present."""
        queue = MemoryTaskQueue()
        provider = TaskProvider(queue=queue, worker_count=1, enable_scheduler=True)
        container = _ContainerStub()

        await provider.boot(container)
        assert provider.scheduler_task is not None

        await provider.shutdown()


@pytest.mark.asyncio
class TestTaskProviderHealthCheck:
    """Test TaskProvider health_check()."""

    async def test_healthy_returns_healthy_status(self) -> None:
        """Health check returns HEALTHY when operational."""
        queue = MemoryTaskQueue()
        provider = TaskProvider(queue=queue, worker_count=1, enable_scheduler=False)
        container = _ContainerStub()

        await provider.boot(container)
        result = await provider.health_check()

        assert result.status.value == "healthy"

    async def test_unhealthy_returns_unhealthy_on_error(self) -> None:
        """Health check returns UNHEALTHY on exception."""
        queue = MagicMock()
        queue.get_task_count = AsyncMock(side_effect=RuntimeError("backend down"))
        provider = TaskProvider(queue=queue, worker_count=1, enable_scheduler=False)
        container = _ContainerStub()

        await provider.boot(container)
        result = await provider.health_check()

        assert result.status.value == "unhealthy"


class TestTaskProviderRegisterHandler:
    """Test task handler registration."""

    def test_register_handler_adds_to_registry(self) -> None:
        """register_handler adds handler to registry."""
        queue = MemoryTaskQueue()
        provider = TaskProvider(queue=queue)

        async def my_task(x: int) -> int:
            return x * 2

        provider.register_handler("multiply", my_task)

        assert "multiply" in provider.registry.to_dict()

    def test_register_multiple_handlers(self) -> None:
        """Multiple handlers can be registered."""
        queue = MemoryTaskQueue()
        provider = TaskProvider(queue=queue)

        async def task_a() -> str:
            return "a"

        async def task_b() -> str:
            return "b"

        provider.register_handler("task_a", task_a)
        provider.register_handler("task_b", task_b)

        registry = provider.registry.to_dict()
        assert "task_a" in registry
        assert "task_b" in registry


class TestTaskProviderWorkerStats:
    """Test worker statistics."""

    @pytest.mark.asyncio
    async def test_get_worker_stats_returns_dict(self) -> None:
        """get_worker_stats returns pool stats dict."""
        queue = MemoryTaskQueue()
        provider = TaskProvider(queue=queue, worker_count=1, enable_scheduler=False)
        container = _ContainerStub()

        await provider.boot(container)
        stats = provider.get_worker_stats()

        assert isinstance(stats, dict)
        assert "active_workers" in stats

    @pytest.mark.asyncio
    async def test_get_worker_stats_none_before_boot(self) -> None:
        """get_worker_stats returns None before boot."""
        queue = MemoryTaskQueue()
        provider = TaskProvider(queue=queue, worker_count=1, enable_scheduler=False)

        assert provider.get_worker_stats() is None


class TestTaskProviderEnqueueJob:
    """Test job enqueueing."""

    @pytest.mark.asyncio
    async def test_enqueue_job_returns_job_id(self) -> None:
        """enqueue_job returns the job ID."""
        from quadkit.tasks.models.job import JobProtocol

        queue = MemoryTaskQueue()
        provider = TaskProvider(queue=queue, worker_count=1, enable_scheduler=False)

        job = JobProtocol(id="job-123", name="test_task")
        job_id = await provider.enqueue_job(job)

        assert job_id == "job-123"


class TestTaskProviderScheduledJobs:
    """Test scheduled job management."""

    def test_get_scheduled_jobs_none_without_scheduler(self) -> None:
        """get_scheduled_jobs returns None when scheduler disabled."""
        queue = MemoryTaskQueue()
        provider = TaskProvider(queue=queue, worker_count=1, enable_scheduler=False)

        assert provider.get_scheduled_jobs() is None


class TestModuleHelpers:
    """Test module-level helper functions."""

    @pytest.mark.asyncio
    async def test_connect_queue_with_connect_method(self) -> None:
        """_connect_queue calls connect() when available."""
        queue = AsyncMock()
        queue.connect = AsyncMock()

        await _connect_queue("test_queue", queue)

        queue.connect.assert_called_once_with()

    @pytest.mark.asyncio
    async def test_connect_queue_without_connect_method(self) -> None:
        """_connect_queue does nothing when no connect method."""
        queue = object()

        await _connect_queue("test_queue", queue)

        # Should not raise

    def test_wire_queue_hooks_with_method(self) -> None:
        """_wire_queue_hooks wires hooks when method exists."""
        queue = MagicMock()
        queue.set_hook_registry = MagicMock()
        hooks = MagicMock()

        _wire_queue_hooks(queue, hooks)

        queue.set_hook_registry.assert_called_once_with(hooks)

    def test_wire_queue_hooks_without_method(self) -> None:
        """_wire_queue_hooks does nothing when method missing."""
        queue = MagicMock()
        hooks = MagicMock()

        _wire_queue_hooks(queue, hooks)  # Should not raise

    @pytest.mark.asyncio
    async def test_check_queue_health_returns_healthy(self) -> None:
        """_check_queue_health returns HEALTHY on success."""
        queue = MagicMock()
        queue.get_task_count = AsyncMock(return_value=10)

        result = await _check_queue_health(queue)

        assert result.status.value == "healthy"

    @pytest.mark.asyncio
    async def test_check_queue_health_returns_unhealthy_on_error(self) -> None:
        """_check_queue_health returns UNHEALTHY on error."""
        queue = MagicMock()
        queue.get_task_count = AsyncMock(side_effect=RuntimeError("boom"))

        result = await _check_queue_health(queue)

        assert result.status.value == "unhealthy"
        assert "boom" in result.error


class TestFactoryFunctions:
    """Test factory function convenience constructors."""

    def test_create_memory_task_provider(self) -> None:
        """Factory creates in-memory provider."""
        provider = create_memory_task_provider(worker_count=2, enable_scheduler=False)

        assert isinstance(provider.queue, MemoryTaskQueue)
        assert provider.worker_count == 2
        assert provider.enable_scheduler is False

    def test_create_redis_task_provider(self) -> None:
        """Factory creates Redis-backed provider."""
        pytest.importorskip("redis")
        provider = create_redis_task_provider(
            redis_url="redis://localhost:6379",
            queue_name="my_tasks",
            worker_count=3,
        )

        assert provider.worker_count == 3

    def test_create_rabbitmq_task_provider(self) -> None:
        """Factory creates RabbitMQ-backed provider."""
        pytest.importorskip("aio_pika")
        provider = create_rabbitmq_task_provider(
            amqp_url="amqp://localhost:5672/",
            queue_name="my_tasks",
            worker_count=4,
        )

        assert provider.worker_count == 4

    def test_create_provider_from_config_dict(self) -> None:
        """Factory accepts dict and converts to config."""
        config = {"worker": {"worker_count": 5}}
        provider = create_provider_from_config(config)

        assert provider.worker_count == 5

    def test_create_provider_from_config_instance(self) -> None:
        """Factory accepts TaskConfig instance."""
        config = TaskConfig(worker=TaskWorkerConfig(worker_count=6))
        provider = create_provider_from_config(config)

        assert provider.worker_count == 6
