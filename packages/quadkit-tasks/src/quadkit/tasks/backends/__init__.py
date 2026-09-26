"""Task queue backend implementations.

This module provides concrete implementations of task queue backends
for different storage systems (memory, Redis, RabbitMQ, Postgres).

Memory backend is always available. Redis, RabbitMQ, and Postgres require optional
dependencies to be installed.
"""

from __future__ import annotations

from quadkit.tasks.backends.memory import MemoryTaskQueue

__all__ = [
    "MemoryTaskQueue",
]

# Optional Postgres backend

# Optional Postgres backend
try:
    from quadkit.tasks.backends.postgres import PostgresTaskQueue

    __all__.append("PostgresTaskQueue")
except (ImportError, AttributeError):
    PostgresTaskQueue = None  # type: ignore[assignment,misc]

# Optional Redis backend
try:
    from quadkit.tasks.backends.redis import RedisTaskQueue

    __all__.append("RedisTaskQueue")
except (ImportError, AttributeError):
    RedisTaskQueue = None  # type: ignore[assignment,misc]

# Optional RabbitMQ backend
try:
    from quadkit.tasks.backends.rabbitmq import RabbitMQTaskQueue

    __all__.append("RabbitMQTaskQueue")
except (ImportError, AttributeError):
    RabbitMQTaskQueue = None  # type: ignore[assignment,misc]
