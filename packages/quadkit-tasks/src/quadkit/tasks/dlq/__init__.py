"""Dead letter queue management for failed tasks."""

from __future__ import annotations

from quadkit.tasks.dlq.backend import (
    DLQBackend,
    InMemoryDLQBackend,
    StateStoreDLQBackend,
)
from quadkit.tasks.dlq.core import DeadLetterQueue, FailureRecord
from quadkit.tasks.dlq.persistent import PersistentDeadLetterQueue
from quadkit.tasks.dlq.redis_dlq import RedisDLQBackend

__all__ = [
    "DLQBackend",
    "DeadLetterQueue",
    "FailureRecord",
    "InMemoryDLQBackend",
    "PersistentDeadLetterQueue",
    "RedisDLQBackend",
    "StateStoreDLQBackend",
]
