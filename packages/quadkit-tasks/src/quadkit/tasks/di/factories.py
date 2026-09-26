"""Factory functions for creating TaskProvider instances.

Convenience constructors for the most common task provider configurations.
Import through ``quadkit.tasks.di`` — the public API is re-exported there.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from quadkit.tasks.di.provider import TaskProvider


def create_provider_from_config(config: Any) -> TaskProvider:
    """Create a TaskProvider from a TaskConfig instance or dict.

    Args:
        config: TaskConfig instance or a dict that will be coerced into one.

    Returns:
        Fully configured TaskProvider.
    """
    from quadkit.tasks.config import TaskConfig
    from quadkit.tasks.di.provider import TaskProvider

    if isinstance(config, dict):
        config = TaskConfig(**config)

    from quadkit.tasks.backends.registry import TaskBackendRegistry

    registry = TaskBackendRegistry.with_defaults()
    queue = registry.create_backend(config)

    return TaskProvider(
        queue=queue,
        worker_count=config.worker.worker_count,
        enable_scheduler=config.scheduler.enabled,
    )


def create_memory_task_provider(
    worker_count: int = 1,
    enable_scheduler: bool = True,
) -> TaskProvider:
    """Create a TaskProvider backed by an in-memory queue.

    Args:
        worker_count: Number of worker coroutines to run concurrently.
        enable_scheduler: Whether to enable the cron job scheduler.

    Returns:
        TaskProvider with MemoryTaskQueue.
    """
    from quadkit.tasks.backends import MemoryTaskQueue
    from quadkit.tasks.di.provider import TaskProvider

    queue = MemoryTaskQueue()  # type: ignore[abstract]
    return TaskProvider(queue, worker_count, enable_scheduler)


def create_redis_task_provider(
    redis_url: str = "redis://localhost:6379",
    queue_name: str = "tasks",
    worker_count: int = 1,
    enable_scheduler: bool = True,
) -> TaskProvider:
    """Create a TaskProvider backed by a Redis queue.

    Args:
        redis_url: Redis connection URL.
        queue_name: Name of the Redis list used as the task queue.
        worker_count: Number of worker coroutines to run concurrently.
        enable_scheduler: Whether to enable the cron job scheduler.

    Returns:
        TaskProvider with RedisTaskQueue.
    """
    from quadkit.tasks.backends import RedisTaskQueue
    from quadkit.tasks.di.provider import TaskProvider

    queue = RedisTaskQueue(redis_url, queue_name)  # type: ignore[abstract]
    return TaskProvider(queue, worker_count, enable_scheduler)


def create_rabbitmq_task_provider(
    amqp_url: str = "amqp://localhost:5672/",
    queue_name: str = "tasks",
    worker_count: int = 1,
    enable_scheduler: bool = True,
) -> TaskProvider:
    """Create a TaskProvider backed by a RabbitMQ queue.

    Args:
        amqp_url: AMQP connection URL.
        queue_name: Name of the AMQP queue.
        worker_count: Number of worker coroutines to run concurrently.
        enable_scheduler: Whether to enable the cron job scheduler.

    Returns:
        TaskProvider with RabbitMQTaskQueue.
    """
    from quadkit.tasks.backends import RabbitMQTaskQueue
    from quadkit.tasks.di.provider import TaskProvider

    queue = RabbitMQTaskQueue(amqp_url, queue_name)  # type: ignore[abstract]
    return TaskProvider(queue, worker_count, enable_scheduler)


__all__ = [
    "create_memory_task_provider",
    "create_provider_from_config",
    "create_rabbitmq_task_provider",
    "create_redis_task_provider",
]
