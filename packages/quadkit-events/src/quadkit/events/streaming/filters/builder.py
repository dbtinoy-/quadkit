"""Fluent builder for event filters."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Any,
)

from quadkit.events.streaming.filters.types import EventFilter

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    from quadkit.contracts.domain import DomainEvent


class FilterBuilder:
    """Fluent builder for constructing event filters."""

    def __init__(self) -> None:
        """Initialize an empty filter builder."""
        self._event_types: list[str] | None = None
        self._aggregate_id: str | None = None
        self._aggregate_id_prefix: str | None = None
        self._aggregate_type: str | None = None
        self._from_timestamp: datetime | None = None
        self._to_timestamp: datetime | None = None
        self._from_version: int | None = None
        self._to_version: int | None = None
        self._metadata_match: dict[str, Any] = {}
        self._custom_predicate: Callable[[DomainEvent], bool] | None = None

    def with_event_types(self, *event_types: str) -> FilterBuilder:
        """Filter by event type names."""
        self._event_types = list(event_types)
        return self

    def with_aggregate_id(self, aggregate_id: str) -> FilterBuilder:
        """Filter by exact aggregate ID."""
        self._aggregate_id = aggregate_id
        return self

    def with_aggregate_id_prefix(self, prefix: str) -> FilterBuilder:
        """Filter by aggregate ID prefix."""
        self._aggregate_id_prefix = prefix
        return self

    def with_aggregate_type(self, aggregate_type: str) -> FilterBuilder:
        """Filter by aggregate type."""
        self._aggregate_type = aggregate_type
        return self

    def after_timestamp(self, timestamp: datetime) -> FilterBuilder:
        """Filter events after a timestamp."""
        self._from_timestamp = timestamp
        return self

    def before_timestamp(self, timestamp: datetime) -> FilterBuilder:
        """Filter events before a timestamp."""
        self._to_timestamp = timestamp
        return self

    def between_timestamps(self, from_ts: datetime, to_ts: datetime) -> FilterBuilder:
        """Filter events between two timestamps."""
        self._from_timestamp = from_ts
        self._to_timestamp = to_ts
        return self

    def from_version(self, version: int) -> FilterBuilder:
        """Filter events from a specific version."""
        self._from_version = version
        return self

    def to_version(self, version: int) -> FilterBuilder:
        """Filter events up to a specific version."""
        self._to_version = version
        return self

    def with_metadata(self, key: str, value: Any) -> FilterBuilder:
        """Filter by metadata key-value pair."""
        self._metadata_match[key] = value
        return self

    def with_predicate(self, predicate: Callable[[DomainEvent], bool]) -> FilterBuilder:
        """Add a custom predicate function."""
        self._custom_predicate = predicate
        return self

    def build(self) -> EventFilter:
        """Build the final EventFilter."""
        return EventFilter(
            event_types=self._event_types,
            aggregate_id=self._aggregate_id,
            aggregate_id_prefix=self._aggregate_id_prefix,
            aggregate_type=self._aggregate_type,
            from_timestamp=self._from_timestamp,
            to_timestamp=self._to_timestamp,
            from_version=self._from_version,
            to_version=self._to_version,
            metadata_match=self._metadata_match if self._metadata_match else None,
            custom_predicate=self._custom_predicate,
        )
