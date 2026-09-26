from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Protocol, TypeVar, runtime_checkable

if TYPE_CHECKING:
    from quadkit.contracts.domain.events import DomainEvent

E = TypeVar("E", bound="DomainEvent")
HandlerFn = Callable[["DomainEvent"], Awaitable[None]]


@runtime_checkable
class EventSerializerProtocol(Protocol):
    """Serializes and deserializes domain events for transport."""

    def serialize(self, event: DomainEvent) -> bytes: ...
    def deserialize(self, data: bytes) -> DomainEvent: ...


@runtime_checkable
class EventFilterProtocol(Protocol):
    """Predicate that determines whether an event should be dispatched."""

    def matches(self, event: DomainEvent) -> bool: ...
