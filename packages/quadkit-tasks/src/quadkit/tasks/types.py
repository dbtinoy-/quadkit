"""Common type definitions for task processing.

This module provides shared types, enums, and data classes used
throughout the task processing system. Following the Root File Pattern,
types are defined at the package root for easy access.
"""

from __future__ import annotations

from enum import Enum, IntEnum


class Priority(IntEnum):
    """Task priority levels for queue ordering (higher number = higher priority).

    The scale is ``0``–``20`` and is **separate** from the kernel's
    ``ProviderPriority`` (``0``–``100``).  Workers dequeue higher-priority
    jobs before lower-priority ones.

    Values:
        LOW (0): Background tasks that can be deferred indefinitely.
        NORMAL (5): Default priority for routine task processing.
        HIGH (10): Time-sensitive tasks processed before NORMAL queue.
        CRITICAL (20): Highest priority; reserved for urgent system tasks.
    """

    LOW = 0
    NORMAL = 5
    HIGH = 10
    CRITICAL = 20


class PoolStrategy(str, Enum):
    """Strategy for compute pool worker management."""

    FIXED = "fixed"
    DYNAMIC = "dynamic"
    ADAPTIVE = "adaptive"


__all__ = ["PoolStrategy", "Priority"]
