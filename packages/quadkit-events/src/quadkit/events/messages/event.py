"""Event message type for Event Sourcing and CQRS.

Events represent facts that have occurred in the past.
They are immutable and stored in the Event Store for rebuilding state.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any

from quadkit.contracts.domain import DomainEvent as _DomainEvent

if TYPE_CHECKING:
    from uuid import UUID

# ``Event`` subclasses the canonical DomainEvent from contracts; we no
# longer export a separate alias here.  Consumers should import
# ``DomainEvent`` directly from ``quadkit.contracts.domain``.


@dataclass(frozen=True)
class Event(_DomainEvent):
    """Represents a fact that happened in the past.

    We override ``__init__`` to accept arbitrary extra keyword arguments,
    which are attached as attributes on the instance.  This preserves the
    historical ability to create ``Event(data=...)`` without declaring a
    new subclass.  ``event_type`` handling is performed by the contract
    base class (which now includes ``actor_id``).

    The event version is an **aggregate-specific** concept and therefore
    is declared on this subclass rather than the canonical ``DomainEvent``
    base class.  ``with_version`` and related helpers operate on this field.
    """

    version: int = 0
    causation_id: UUID | None = None
    correlation_id: UUID | None = None

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        # ``_DomainEvent`` defines the standard fields used for storage.
        base_fields = {f.name for f in _DomainEvent.__dataclass_fields__.values()}
        base_kwargs: dict[str, Any] = {}
        extras: dict[str, Any] = {}
        for k, v in kwargs.items():
            if k in base_fields:
                base_kwargs[k] = v
            else:
                extras[k] = v
        super().__init__(*args, **base_kwargs)
        for k, v in extras.items():
            object.__setattr__(self, k, v)

    def with_version(self, version: int) -> Event:
        """Create a copy with a specific version (aggregate version)."""
        return replace(self, version=version)

    def for_aggregate(self, aggregate_id: UUID, aggregate_type: str) -> Event:
        """Create a copy for a specific aggregate."""
        return replace(
            self,
            aggregate_id=aggregate_id,
            aggregate_type=aggregate_type,
        )


@dataclass(frozen=True)
class IntegrationEvent(Event):
    """Event for cross-service communication."""

    source_service: str = ""
    destination_services: list[str] = field(default_factory=list)


__all__ = [
    "Event",
    "IntegrationEvent",
]
