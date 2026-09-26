"""
Utility functions for MongoDB event store operations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    from quadkit.events.messages.event import Event


def serialize_event(event: Event, serializer: Any | None = None) -> dict[str, Any]:
    """Serialize an event to dict."""
    if serializer:
        from typing import cast

        # Cast serializer return to declared dict type for typing
        return cast("dict[str, Any]", serializer.serialize(event))

    if hasattr(event, "model_dump"):
        from typing import cast

        return cast("dict[str, Any]", event.model_dump(mode="json"))
    return dict(getattr(event, "__dict__", {}))


def deserialize_event(doc: dict[str, Any], serializer: Any | None = None) -> Event:
    """Deserialize an event from MongoDB document."""
    if serializer:
        from typing import cast

        from quadkit.events.messages.event import Event as _Event

        return cast(
            "_Event",
            serializer.deserialize(doc["event_type"], doc["event_data"]),
        )

    from typing import cast

    from quadkit.events.messages.event import Event as _Event

    event_data = doc["event_data"]
    data = {**event_data}
    # Ensure id and timestamp are provided to Pydantic model
    data["id"] = UUID(doc["event_id"]) if doc.get("event_id") else data.get("id")
    data["timestamp"] = doc.get("timestamp") or data.get("timestamp")

    # Typecast the result to Event to satisfy static analyzers
    return cast("_Event", _Event.deserialize(doc["event_type"], data))  # type: ignore[attr-defined]
