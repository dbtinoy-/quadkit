"""Composite event filters."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from quadkit.events.constants import FilterOperator

if TYPE_CHECKING:
    from quadkit.contracts.domain import DomainEvent
    from quadkit.events.streaming.filters.types import EventFilter


@dataclass
class CompositeFilter:
    """Composite filter combining multiple filters."""

    filters: list[EventFilter | CompositeFilter] = field(default_factory=list)
    operator: str = FilterOperator.AND  # "and" or "or"

    def matches(self, event: DomainEvent) -> bool:
        """Check if event matches the composite filter."""
        if self.operator == FilterOperator.AND:
            return all(f.matches(event) for f in self.filters)
        return any(f.matches(event) for f in self.filters)

    def __and__(self, other: EventFilter | CompositeFilter) -> CompositeFilter:
        """Add another filter with AND logic."""
        if self.operator == FilterOperator.AND:
            return CompositeFilter(
                filters=[*self.filters, other], operator=FilterOperator.AND
            )
        return CompositeFilter(filters=[self, other], operator=FilterOperator.AND)

    def __or__(self, other: EventFilter | CompositeFilter) -> CompositeFilter:
        """Add another filter with OR logic."""
        if self.operator == FilterOperator.OR:
            return CompositeFilter(
                filters=[*self.filters, other], operator=FilterOperator.OR
            )
        return CompositeFilter(filters=[self, other], operator=FilterOperator.OR)


@dataclass
class NegatedFilter:
    """Filter that negates another filter."""

    inner: EventFilter | CompositeFilter

    def matches(self, event: DomainEvent) -> bool:
        """Check if event does NOT match the inner filter."""
        return not self.inner.matches(event)
