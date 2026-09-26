"""Event filtering base classes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    from quadkit.contracts.domain import DomainEvent
    from quadkit.events.streaming.filters.composite import (
        CompositeFilter,
        NegatedFilter,
    )


@dataclass
class EventFilter:
    """Filter events by various criteria.

    Attributes:
        event_types: List of event type names to include.
        aggregate_id: Exact aggregate ID to match.
        aggregate_id_prefix: Prefix for aggregate ID matching.
        aggregate_type: Type of aggregate to match.
        from_timestamp: Include events after this time.
        to_timestamp: Include events before this time.
        from_version: Include events with version >= this.
        to_version: Include events with version <= this.
        metadata_match: Dict of metadata key-value pairs to match.
        custom_predicate: Custom filter function.
    """

    event_types: list[str] | None = None
    aggregate_id: str | None = None
    aggregate_id_prefix: str | None = None
    aggregate_type: str | None = None
    from_timestamp: datetime | None = None
    to_timestamp: datetime | None = None
    from_version: int | None = None
    to_version: int | None = None
    metadata_match: dict[str, Any] | None = None
    custom_predicate: Callable[[DomainEvent], bool] | None = None

    def matches(self, event: DomainEvent) -> bool:
        """Check if an event matches this filter."""
        # Event type filter
        if self.event_types:
            event_type = type(event).__name__
            if event_type not in self.event_types:
                return False

        # Aggregate ID filter
        if self.aggregate_id is not None:
            event_agg_id = getattr(event, "aggregate_id", None)
            if event_agg_id != self.aggregate_id:
                return False

        # Aggregate ID prefix filter
        if self.aggregate_id_prefix is not None:
            event_agg_id = getattr(event, "aggregate_id", None)
            if event_agg_id is None or not str(event_agg_id).startswith(
                self.aggregate_id_prefix,
            ):
                return False

        # Aggregate type filter
        if self.aggregate_type is not None:
            event_agg_type = getattr(event, "aggregate_type", None)
            if event_agg_type != self.aggregate_type:
                return False

        # Timestamp filters
        event_timestamp = getattr(event, "timestamp", None) or getattr(
            event,
            "occurred_at",
            None,
        )

        if (
            self.from_timestamp is not None
            and event_timestamp
            and event_timestamp < self.from_timestamp
        ):
            return False

        if (
            self.to_timestamp is not None
            and event_timestamp
            and event_timestamp > self.to_timestamp
        ):
            return False

        # Version filters
        event_version = getattr(event, "version", None)

        if (
            self.from_version is not None
            and event_version is not None
            and event_version < self.from_version
        ):
            return False

        if (
            self.to_version is not None
            and event_version is not None
            and event_version > self.to_version
        ):
            return False

        # Metadata match
        if self.metadata_match:
            event_metadata = getattr(event, "metadata", None) or {}
            for key, value in self.metadata_match.items():
                if event_metadata.get(key) != value:
                    return False

        # Custom predicate
        if self.custom_predicate is not None and not self.custom_predicate(event):
            return False

        return True

    def __and__(self, other: EventFilter) -> CompositeFilter:
        """Combine two filters with AND logic."""
        from quadkit.events.streaming.filters.composite import CompositeFilter

        return CompositeFilter(filters=[self, other], operator="and")

    def __or__(self, other: EventFilter) -> CompositeFilter:
        """Combine two filters with OR logic."""
        from quadkit.events.streaming.filters.composite import CompositeFilter

        return CompositeFilter(filters=[self, other], operator="or")

    def __invert__(self) -> NegatedFilter:
        """Negate this filter."""
        from quadkit.events.streaming.filters.composite import NegatedFilter

        return NegatedFilter(inner=self)
