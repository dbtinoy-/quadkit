"""Event filter factory functions for streaming."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.events.streaming.filters.types import EventFilter

if TYPE_CHECKING:
    from datetime import datetime


def type_filter(*event_types: str) -> EventFilter:
    """Create a filter for specific event types."""
    return EventFilter(event_types=list(event_types))


def aggregate_filter(aggregate_id: str) -> EventFilter:
    """Create a filter for a specific aggregate."""
    return EventFilter(aggregate_id=aggregate_id)


def time_range_filter(
    from_timestamp: datetime | None = None,
    to_timestamp: datetime | None = None,
) -> EventFilter:
    """Create a filter for a time range."""
    return EventFilter(from_timestamp=from_timestamp, to_timestamp=to_timestamp)


def metadata_filter(**metadata: Any) -> EventFilter:
    """Create a filter for metadata values."""
    return EventFilter(metadata_match=metadata)


__all__ = [
    "aggregate_filter",
    "metadata_filter",
    "time_range_filter",
    "type_filter",
]
