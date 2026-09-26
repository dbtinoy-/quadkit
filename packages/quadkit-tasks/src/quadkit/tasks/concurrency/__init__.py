"""Concurrency utilities for task processing.

This module provides concurrency controls for task execution:
- Process-local locking for task deduplication (``LockManager``)
- Cross-process locking backed by the application database
  (``DatabaseLockManager``) — see :mod:`quadkit.tasks.concurrency.database_locking`
- Rate limiting for throughput control
"""

from __future__ import annotations

from quadkit.tasks.concurrency.compute import (
    Compute,
    ComputePool,
    PoolMetrics,
    ProcessStats,
)
from quadkit.tasks.concurrency.database_locking import (
    DatabaseLockHandle,
    DatabaseLockManager,
    LockSnapshot,
    default_holder_id,
)
from quadkit.tasks.concurrency.locking import (
    InMemoryLock as DistributedLockProtocol,
)
from quadkit.tasks.concurrency.locking import (
    UniqueTask,
    distributed_lock,
)
from quadkit.tasks.concurrency.rate_limit import (
    GlobalRateLimiter,
    QueueRateLimiter,
)

__all__ = [
    # Compute
    "Compute",
    "ComputePool",
    # Database locking (cross-process)
    "DatabaseLockHandle",
    "DatabaseLockManager",
    "DistributedLockProtocol",
    "GlobalRateLimiter",
    "LockSnapshot",
    "PoolMetrics",
    "ProcessStats",
    "QueueRateLimiter",
    "UniqueTask",
    "default_holder_id",
    "distributed_lock",
]
