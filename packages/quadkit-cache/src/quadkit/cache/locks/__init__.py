"""Distributed locking utilities for Quadkit cache.

Provides distributed locks with automatic TTL renewal.
"""

from __future__ import annotations

from quadkit.cache.locks.distributed import (
    DistributedLockInfo,
    DistributedLockProtocol,
)
from quadkit.cache.locks.manager import LockManager

__all__ = [
    "DistributedLockInfo",
    "DistributedLockProtocol",
    "LockManager",
]
