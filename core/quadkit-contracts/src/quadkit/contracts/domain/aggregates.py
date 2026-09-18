"""Aggregate root protocol.

The concrete ``AggregateRoot`` base class lives in ``quadkit.domain.models.aggregate``
(the core ``quadkit`` package).  Contracts expose only the structural protocol
so that any package can type-check against it without pulling in implementation
code.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from quadkit.contracts.domain.events import DomainEvent


@runtime_checkable
class AggregateRootProtocol(Protocol):
    """Structural protocol for aggregate root objects.

    Any class that implements event buffering and consistency boundaries
    satisfies this protocol.  Type-check against it instead of the concrete
    ``AggregateRoot`` base class where possible.
    """

    def add_event(self, event: DomainEvent) -> None:
        """Register a domain event with the aggregate."""
        ...

    def collect_events(self) -> list[DomainEvent]:
        """Return and clear all buffered domain events."""
        ...

    def pull_events(self) -> list[DomainEvent]:
        """Return buffered events without clearing them."""
        ...

    def clear_events(self) -> None:
        """Discard all buffered domain events."""
        ...

    @property
    def has_uncommitted_events(self) -> bool:
        """Return True when there are buffered events not yet published."""
        ...


__all__ = ["AggregateRootProtocol"]
