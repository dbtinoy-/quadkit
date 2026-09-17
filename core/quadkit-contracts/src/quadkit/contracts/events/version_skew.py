"""Event version-skew data types for LXF-006.

Defines the type for declaring a known event version pair and the two
alert payloads emitted when an unknown type or version is received.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class EventTypeVersion:
    """A known event type + schema version pair that a consumer declares."""

    event_type: str
    schema_version: int


@dataclass(frozen=True, slots=True)
class UnknownEventTypeReceived:
    """Emitted when an incoming event has a type not in the consumer's known set."""

    consumer_id: str
    event_type: str
    schema_version: int
    event_id: str
    tenant_id: str | None
    received_at: datetime


@dataclass(frozen=True, slots=True)
class EventSchemaVersionSkew:
    """Emitted when an incoming event type is known but its version is not."""

    consumer_id: str
    event_type: str
    received_version: int
    known_versions: frozenset[int]
    upcast_attempted: bool
    event_id: str
    tenant_id: str | None
    received_at: datetime


__all__ = [
    "EventSchemaVersionSkew",
    "EventTypeVersion",
    "UnknownEventTypeReceived",
]
