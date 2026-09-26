"""SQLite event serialization utilities."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, cast
from uuid import UUID

from quadkit.logging import get_logger
from quadkit.serialization import loads

if TYPE_CHECKING:
    from quadkit.events.messages.event import Event
    from quadkit.events.messages.event import Event as _EventType

logger = get_logger(__name__)


class SqliteEventSerializer:
    """Handles serialization and deserialization of events for SQLite storage."""

    def __init__(self, event_serializer: Any | None = None) -> None:
        """Initialize the serializer.

        Args:
            event_serializer: Optional custom event serializer.
        """
        self.event_serializer = event_serializer
        self._event_type_registry: dict[str, type] = {}

    def register_event_type(self, event_type: str, event_class: type) -> None:
        """Register an event type for proper deserialization.

        Args:
            event_type: Event type name.
            event_class: Event class to instantiate.
        """
        self._event_type_registry[event_type] = event_class

    def serialize_event(self, event: Event) -> dict[str, Any]:
        """Serialize an event to dict."""
        if self.event_serializer:
            # event_serializer may return Any; cast to the declared return type
            return cast("dict[str, Any]", self.event_serializer.serialize(event))

        if hasattr(event, "model_dump"):
            data: dict[str, Any] = event.model_dump(mode="json")
            # Convert nested pydantic models (like metadata) to dicts
            if "metadata" in data and hasattr(data["metadata"], "model_dump"):
                data["metadata"] = data["metadata"].model_dump(mode="json")
            return data
        return dict(getattr(event, "__dict__", {}))

    def deserialize_event(self, row: dict[str, Any]) -> Event:
        """Deserialize an event from database row."""
        if self.event_serializer:
            # AsyncStringSerializerProtocol returns Any — cast to Event for typing
            return cast(
                "_EventType",
                self.event_serializer.deserialize(row["event_type"], row["event_data"]),
            )

        # Try registered event type first
        event_type = row["event_type"]
        if event_type in self._event_type_registry:
            event_class = self._event_type_registry[event_type]
            event_data = loads(row["event_data"].encode("utf-8"))
            # Cast to Event to satisfy static typing

            return cast("_EventType", event_class(**event_data))

        # Fall back to generic DomainEvent
        from quadkit.contracts.domain import DomainEvent

        event_data = loads(row["event_data"].encode("utf-8"))

        # Remove fields that will be set separately to avoid duplicates
        event_data.pop("timestamp", None)
        event_data.pop("id", None)

        timestamp = row["timestamp"]
        if isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp)
            except (ValueError, TypeError) as e:
                logger.debug("Failed to parse timestamp %r: %s", timestamp, e)

        event_id = row["event_id"]
        if isinstance(event_id, str):
            try:
                event_id = UUID(event_id)
            except (ValueError, TypeError) as e:
                logger.debug("Failed to parse event_id %r: %s", event_id, e)

        occurred_at = event_data.get("occurred_at", timestamp)
        data = {
            **event_data,
            "id": event_id,
            "timestamp": timestamp,
            "occurred_at": occurred_at,
        }
        # Cast DomainEvent to Event for typing

        return cast("_EventType", DomainEvent(**data))


__all__ = ["SqliteEventSerializer"]
