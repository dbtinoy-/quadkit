"""Base message classes for Event Sourcing and CQRS.

This module defines the foundational Message class and MessageMetadata
that all messages inherit from. These are defined in contracts to allow
cross-package interoperability without direct sibling dependencies.

Also defines MessageSerializerProtocol for serializing/deserializing events.
"""

from __future__ import annotations

from dataclasses import MISSING, asdict, dataclass, field, replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Generic, Protocol, TypeVar, runtime_checkable
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from quadkit.contracts.domain import DomainModelProtocol

TResult = TypeVar("TResult")


@runtime_checkable
class MessageSerializerProtocol(Protocol):
    """Protocol for serializing and deserializing messages.

    Different message formats (JSON, Avro, Protobuf) can implement
    this protocol to provide serialization for event stores and message buses.
    """

    def serialize(self, message: Message) -> bytes:
        """Serialize a message to bytes.

        Args:
            message: Message to serialize.

        Returns:
            Serialized message bytes.
        """
        ...

    def deserialize(self, data: bytes, message_type: type[Message]) -> Message:
        """Deserialize bytes to a message.

        Args:
            data: Serialized message bytes.
            message_type: Type of message to deserialize to.

        Returns:
            Deserialized message instance.
        """
        ...

    def serialize_event(self, event: DomainModelProtocol) -> bytes:
        """Serialize a domain event to bytes.

        Args:
            event: Domain event to serialize.

        Returns:
            Serialized event bytes.
        """
        ...

    def deserialize_event(
        self, data: bytes, event_type: type[DomainModelProtocol]
    ) -> DomainModelProtocol:
        """Deserialize bytes to a domain event.

        Args:
            data: Serialized event bytes.
            event_type: Type of event to deserialize to.

        Returns:
            Deserialized event instance.
        """
        ...


@dataclass(frozen=True)
class MessageMetadata:
    """Metadata attached to messages for tracking and correlation."""

    correlation_id: UUID | None = None
    causation_id: UUID | None = None
    user_id: str | None = None
    tenant_id: str | None = None
    trace_id: str | None = None
    span_id: str | None = None
    custom: dict[str, Any] = field(default_factory=dict)

    def with_correlation(self, correlation_id: UUID) -> MessageMetadata:
        """Create new metadata with correlation ID."""
        return replace(self, correlation_id=correlation_id)

    def with_causation(self, causation_id: UUID) -> MessageMetadata:
        """Create new metadata with causation ID."""
        return replace(self, causation_id=causation_id)

    def with_user(self, user_id: str) -> MessageMetadata:
        """Create new metadata with user ID."""
        return replace(self, user_id=user_id)

    def with_tenant(self, tenant_id: str) -> MessageMetadata:
        """Create new metadata with tenant ID."""
        return replace(self, tenant_id=tenant_id)

    def with_custom(self, key: str, value: Any) -> MessageMetadata:
        """Create new metadata with additional custom field."""
        new_custom = {**self.custom, key: value}
        return replace(self, custom=new_custom)


@dataclass(frozen=True)
class Message:
    """Base class for all messages in the Events system."""

    id: UUID = field(default_factory=uuid4)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: MessageMetadata = field(default_factory=MessageMetadata)

    def with_metadata(self, metadata: MessageMetadata) -> Message:
        """Create a copy of the message with new metadata."""
        return replace(self, metadata=metadata)

    def with_correlation_id(self, correlation_id: UUID) -> Message:
        """Create a copy with a correlation ID."""
        new_metadata = self.metadata.with_correlation(correlation_id)
        return self.with_metadata(new_metadata)

    def with_causation_id(self, causation_id: UUID) -> Message:
        """Create a copy with a causation ID."""
        new_metadata = self.metadata.with_causation(causation_id)
        return self.with_metadata(new_metadata)

    @property
    def correlation_id(self) -> UUID | None:
        """Get correlation ID from metadata."""
        return self.metadata.correlation_id

    @property
    def causation_id(self) -> UUID | None:
        """Get causation ID from metadata."""
        return self.metadata.causation_id

    def to_dict(self) -> dict[str, Any]:
        """Convert message to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Message:
        """Create message from dictionary."""
        return cls(**data)


# ``Event`` and ``DomainEventContext`` were removed in the 2026 refactor.
# ``DomainEvent`` in ``quadkit.contracts.domain.events`` now serves as the
# single canonical representation of domain events, with an optional
# ``actor_id`` field replacing the earlier context wrapper.


@dataclass(frozen=True)
class Query(Message, Generic[TResult]):
    """Represents a request for data."""

    include_deleted: bool = False
    cache_key: str | None = None
    skip_cache: bool = False


@dataclass(frozen=True)
class PaginatedQuery(Query[TResult]):
    """Query with built-in pagination support."""

    page: int = 1
    page_size: int = 20
    sort_by: str | None = None
    sort_desc: bool = False


@dataclass(init=False, frozen=True)
class Command(Message, Generic[TResult]):
    """Represents an intent to change state.

    A frozen dataclass that accepts all declared fields as keyword arguments,
    plus any extra kwargs (stored as object attributes for forward-compatibility).
    We intentionally disable dataclass-generated ``__init__`` and supply our
    own so that subclasses can be instantiated with their specific fields without
    receiving ``TypeError`` for unknown extras.

    Note: This class intentionally does *not* inherit from ``DomainModel``
    (which lives in ``quadkit``, not ``quadkit-contracts``) to avoid a
    circular dependency.  All dataclass bookkeeping is done directly here.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        dc_fields = getattr(self.__class__, "__dataclass_fields__", {})
        for fname, f in dc_fields.items():
            if fname in kwargs:
                object.__setattr__(self, fname, kwargs.pop(fname))
            elif f.default is not MISSING:
                object.__setattr__(self, fname, f.default)
            elif f.default_factory is not MISSING:
                object.__setattr__(self, fname, f.default_factory())
            # else: required field not provided — TypeError raised naturally
        # Store any remaining extra kwargs as attributes (forward compatibility)
        for k, v in kwargs.items():
            object.__setattr__(self, k, v)


@dataclass(frozen=True)
class IdempotentCommand(Command[TResult]):
    """Represents a command that can be safely retried."""

    idempotency_key: str | None = None


__all__ = [
    "Command",
    "IdempotentCommand",
    "Message",
    "MessageMetadata",
    "MessageSerializerProtocol",
    "PaginatedQuery",
    "Query",
]
