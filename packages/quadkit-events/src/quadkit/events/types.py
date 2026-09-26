"""Type definitions for quadkit-events."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, TypeVar
from uuid import UUID, uuid4


# --- Enums (moved from enums.py) ---
class MessageType(StrEnum):
    """Types of messages in the event-driven system."""

    COMMAND = "command"
    QUERY = "query"
    EVENT = "event"


class AggregateStatus(StrEnum):
    """Status of an aggregate root."""

    ACTIVE = "active"
    DELETED = "deleted"
    ARCHIVED = "archived"


class SagaState(StrEnum):
    """States of a saga execution."""

    NOT_STARTED = "not_started"
    STARTED = "started"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"
    TIMED_OUT = "timed_out"
    COMPENSATION_FAILED = "compensation_failed"
    PENDING = "pending"


class ProjectionState(StrEnum):
    """States of a projection."""

    STOPPED = "stopped"
    RUNNING = "running"
    CATCHING_UP = "catching_up"
    LIVE = "live"
    FAULTED = "faulted"
    REBUILDING = "rebuilding"


class StreamPosition(StrEnum):
    """Starting position for event streams."""

    START = "start"
    END = "end"
    LIVE = "live"


class EventStoreBackend(StrEnum):
    """Supported event store backends."""

    MEMORY = "memory"
    POSTGRES = "postgres"
    MONGODB = "mongodb"
    SQLITE = "sqlite"


class SnapshotStrategy(StrEnum):
    """Snapshot creation strategies."""

    EVENT_COUNT = "event_count"
    TIME_BASED = "time_based"
    ON_DEMAND = "on_demand"


class EventStatus(StrEnum):
    """Status of an event."""

    PENDING = "pending"
    PROCESSED = "processed"
    FAILED = "failed"


class EventSource(StrEnum):
    """Source of an event."""

    USER = "user"
    SYSTEM = "system"
    EXTERNAL = "external"


__all__ = [
    "AggregateStatus",
    "EventSource",
    "EventStatus",
    "EventStoreBackend",
    "MessageType",
    "ProjectionState",
    "SagaState",
    "SnapshotStrategy",
    "StreamPosition",
]


from quadkit.contracts.domain import DomainEvent
from quadkit.domain import DomainModel
from quadkit.events.messages import (
    Command,
    Event,
    IdempotentCommand,
    IntegrationEvent,
    Message,
    MessageMetadata,
    Query,
)
from quadkit.validation import Field

T = TypeVar("T")
TCommand = TypeVar("TCommand", bound="Command")
TQuery = TypeVar("TQuery", bound="Query")
TEvent = TypeVar("TEvent", bound="Event")
TResult = TypeVar("TResult")


@dataclass(init=False)
class EventEnvelope(DomainModel):
    """Wrapper for events with metadata for storage and transmission."""

    stream_id: str
    event_type: str
    event_data: dict[str, Any]
    version: int
    event_id: UUID = Field(default_factory=uuid4)
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    correlation_id: UUID | None = None
    causation_id: UUID | None = None


@dataclass(init=False)
class Snapshot(DomainModel):
    """Aggregate state snapshot for performance optimization."""

    aggregate_id: UUID
    aggregate_type: str
    version: int
    state: dict[str, Any]
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)


@dataclass(init=False)
class StreamInfo(DomainModel):
    """Information about an event stream."""

    stream_id: str
    aggregate_type: str | None = None
    version: int = 0
    event_count: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(init=False)
class Checkpoint(DomainModel):
    """Checkpoint for tracking projection progress."""

    projection_name: str
    stream_position: int = 0
    last_processed_event_id: UUID | None = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


@dataclass(init=False)
class SagaData(DomainModel):
    """Persisted saga state data."""

    saga_id: UUID
    saga_type: str
    state: SagaState = SagaState.NOT_STARTED
    current_step: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    failed_at: datetime | None = None
    error_message: str | None = None
    completed_steps: list[str] = Field(default_factory=list)
    compensated_steps: list[str] = Field(default_factory=list)


@dataclass(init=False)
class CommandResult(DomainModel):
    """Result of command execution."""

    success: bool
    data: dict[str, Any] | None = None
    error: str | None = None
    events: list[Event] = Field(default_factory=list)


@dataclass(init=False)
class QueryResult(DomainModel):
    """Result of query execution."""

    success: bool
    data: Any | None = None
    error: str | None = None
    cached: bool = False


@dataclass(init=False)
class HandlerInfo(DomainModel):
    """Information about a registered handler."""

    handler_type: str
    message_type: str
    handler_class: str
    registered_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


@dataclass(init=False)
class MiddlewareInfo(DomainModel):
    """Information about registered middleware."""

    name: str
    order: int
    enabled: bool = True


__all__ = [
    "Checkpoint",
    "Command",
    "CommandResult",
    "DomainEvent",
    "Event",
    "EventEnvelope",
    "HandlerInfo",
    "IdempotentCommand",
    "IntegrationEvent",
    "Message",
    "MessageMetadata",
    "MiddlewareInfo",
    "Query",
    "QueryResult",
    "SagaData",
    "Snapshot",
    "StreamInfo",
]
