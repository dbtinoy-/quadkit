"""Base classes for aggregate roots."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypeVar

from quadkit.contracts.domain.events import DomainEvent
from quadkit.domain.models.entity import Entity

T = TypeVar("T", bound=DomainEvent)


@dataclass(init=False)
class AggregateRoot(Entity):
    """
    Base class for aggregate roots.

    An aggregate root is the entry point for a cluster of associated
    objects. It maintains consistency boundaries and publishes
    domain events.

    Satisfies :class:`~quadkit.contracts.domain.aggregates.AggregateRootProtocol`.
    """

    _pending_events: list[DomainEvent] = field(
        default_factory=list, init=False, repr=False
    )

    def _record_event(self, event: DomainEvent) -> None:
        """Record a domain event to be published later (internal helper)."""
        self._pending_events.append(event)

    # ------------------------------------------------------------------
    # AggregateRootProtocol public interface
    # ------------------------------------------------------------------

    def add_event(self, event: DomainEvent) -> None:
        """Register a domain event with the aggregate."""
        self._record_event(event)

    def collect_events(self) -> list[DomainEvent]:
        """Return and clear all buffered domain events."""
        events = list(self._pending_events)
        self._pending_events.clear()
        return events

    def pull_events(self) -> list[DomainEvent]:
        """Return buffered events without clearing them."""
        return list(self._pending_events)

    def clear_events(self) -> None:
        """Discard all buffered domain events."""
        self._pending_events.clear()

    @property
    def has_uncommitted_events(self) -> bool:
        """Return True when there are buffered events not yet published."""
        return bool(self._pending_events)


@dataclass(init=False)
class VersionedAggregate(AggregateRoot):
    """
    Aggregate root with optimistic concurrency control via versioning.
    """

    version: int = field(default=0, metadata={"_quadkit_field": True})

    def _increment_version(self) -> None:
        """Increment the aggregate version."""
        self.version += 1


@dataclass(init=False)
class EventSourcedAggregate(VersionedAggregate):
    """
    Aggregate root that reconstructs its state from a stream of events.
    """

    def apply(self, event: DomainEvent, record: bool = True) -> None:
        """
        Apply an event to the aggregate.

        If ``record`` is True, the event is added to pending events.
        """
        handler_name = f"on_{self._to_snake_case(type(event).__name__)}"
        handler = getattr(self, handler_name, None)

        if handler:
            handler(event)

        if record:
            self._increment_version()
            # Ensure event has metadata
            if not event.aggregate_id:
                object.__setattr__(event, "aggregate_id", self.id)
            if not event.aggregate_type:
                object.__setattr__(event, "aggregate_type", type(self).__name__)
            object.__setattr__(event, "sequence_number", self.version)

            self._record_event(event)

    @staticmethod
    def _to_snake_case(name: str) -> str:
        import re

        return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
