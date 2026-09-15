"""Configuration models for the memory subsystem.

Contains :class:`MemoryConfig`, which controls in-memory data-structure
capacities for repositories, event buses, outboxes, and audit logs.
"""

from __future__ import annotations

from dataclasses import dataclass

from quadkit.testing.memory.constants import (
    DEFAULT_AUDIT_CAPACITY,
    DEFAULT_EVENT_BUS_CAPACITY,
    DEFAULT_OUTBOX_CAPACITY,
    DEFAULT_REPOSITORY_CAPACITY,
)


@dataclass
class MemoryConfig:
    """In-memory implementations of common framework protocols configuration."""

    repository_capacity: int = DEFAULT_REPOSITORY_CAPACITY
    # consumed by: InMemoryRepository max-entry count
    event_bus_capacity: int = DEFAULT_EVENT_BUS_CAPACITY
    # consumed by: InMemoryEventBus queue depth
    outbox_capacity: int = DEFAULT_OUTBOX_CAPACITY
    # consumed by: InMemoryOutbox max-entry count
    audit_capacity: int = DEFAULT_AUDIT_CAPACITY
    # consumed by: InMemoryAuditLogger max-entry count


__all__ = ["MemoryConfig"]
