"""Constants for the memory subsystem.

Typed defaults for in-memory data-structure capacities.
"""

from __future__ import annotations

import importlib.metadata

try:
    __version__: str = importlib.metadata.version("quadkit")
except ImportError:
    __version__ = "0.0.0"

# -- Environment Variable Prefix -------------------------------------------

ENV_PREFIX: str = "QK_MEMORY_"
"""Environment variable prefix for memory configuration."""

# -- Capacity Defaults -------------------------------------------------------

DEFAULT_REPOSITORY_CAPACITY: int = 10_000
"""Max entries stored by InMemoryRepository; consumed by: InMemoryRepository."""

DEFAULT_EVENT_BUS_CAPACITY: int = 1_000
"""Default InMemoryEventBus queue depth; consumed by: InMemoryEventBus."""

DEFAULT_OUTBOX_CAPACITY: int = 5_000
"""Max entries stored by InMemoryOutbox; consumed by: InMemoryOutbox."""

DEFAULT_AUDIT_CAPACITY: int = 10_000
"""Max entries stored by InMemoryAuditLogger; consumed by: InMemoryAuditLogger."""

__all__ = [
    "DEFAULT_AUDIT_CAPACITY",
    "DEFAULT_EVENT_BUS_CAPACITY",
    "DEFAULT_OUTBOX_CAPACITY",
    "DEFAULT_REPOSITORY_CAPACITY",
    "ENV_PREFIX",
    "__version__",
]
