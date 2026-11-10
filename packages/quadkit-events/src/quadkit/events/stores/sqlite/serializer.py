"""SQLite event serialization utilities."""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, cast
from uuid import UUID

from quadkit.events.exceptions import EventStoreError
from quadkit.logging import get_logger
from quadkit.serialization import dumps, loads

if TYPE_CHECKING:
    from quadkit.events.messages.event import Event
    from quadkit.events.messages.event import Event as _EventType

logger = get_logger(__name__)


def _payload_preserved(original: Any, rebuilt: Any) -> bool:
    """Check persisted JSON values survive; newly supplied defaults are allowed."""
    if isinstance(original, dict):
        return isinstance(rebuilt, dict) and all(
            key in rebuilt and _payload_preserved(value, rebuilt[key])
            for key, value in original.items()
        )
    if isinstance(original, list):
        return (
            isinstance(rebuilt, list)
            and len(original) == len(rebuilt)
            and all(
                _payload_preserved(left, right)
                for left, right in zip(original, rebuilt, strict=True)
            )
        )
    return type(original) is type(rebuilt) and original == rebuilt


def _event_uuid(value: Any) -> UUID:
    """Parse an event UUID without accepting nulls or coercing arbitrary values."""
    try:
        if isinstance(value, UUID):
            return value
        if isinstance(value, str):
            return UUID(value)
    except ValueError as exc:
        raise EventStoreError("SQLite event identity is invalid") from exc
    raise EventStoreError("SQLite event identity is invalid")


def validate_event_identity(
    event_data: dict[str, Any], row_id: Any, *, allow_missing: bool = False
) -> UUID:
    """Check the default DomainEvent payload against the row's event ID.

    Older payloads that omitted an ID can recover it from the authoritative row.
    This validates identity agreement, not that either value is authentic.
    """
    event_id = _event_uuid(row_id)
    if "event_id" not in event_data:
        if not allow_missing:
            raise EventStoreError("SQLite event identity is missing from payload")
        event_data["event_id"] = str(event_id)
    elif _event_uuid(event_data["event_id"]) != event_id:
        raise EventStoreError("SQLite event identity does not match its row")
    return event_id


def _checked_domain_event(event: Any, expected_id: UUID) -> Any:
    actual_id = getattr(event, "event_id", None)
    if not isinstance(actual_id, UUID) or actual_id != expected_id:
        raise EventStoreError("Restored SQLite event identity does not match its row")
    return event


def _restore_legacy_base_fields(
    data: dict[str, Any], *, has_event_fields: bool
) -> dict[str, Any]:
    """Restore known base fields without discarding dynamic legacy attributes."""
    values = dict(data)
    names = ["event_id", "aggregate_id"]
    if has_event_fields:
        names.extend(("causation_id", "correlation_id"))
    for name in names:
        if isinstance(values.get(name), str):
            values[name] = UUID(values[name])
    if isinstance(values.get("occurred_at"), str):
        values["occurred_at"] = datetime.fromisoformat(values["occurred_at"])
    return values


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
        data = dict(getattr(event, "__dict__", {}))
        if is_dataclass(event) and not isinstance(event, type):
            # Slots may not be present in __dict__; preserve extras as well.
            for event_field in fields(event):
                data[event_field.name] = getattr(event, event_field.name)
        return data

    def deserialize_event(self, row: dict[str, Any]) -> Event:
        """Deserialize an event from database row."""
        if self.event_serializer:
            # AsyncStringSerializerProtocol returns Any — cast to Event for typing
            return cast(
                "_EventType",
                self.event_serializer.deserialize(row["event_type"], row["event_data"]),
            )

        from quadkit.contracts.domain import DomainEvent
        from quadkit.events.messages.event import Event

        event_type = row["event_type"]
        event_data = loads(row["event_data"].encode("utf-8"))
        if not isinstance(event_data, dict):
            raise EventStoreError("SQLite event payload must be an object")

        event_class = self._event_type_registry.get(event_type)
        domain_payload = event_type not in self._event_type_registry or (
            isinstance(event_class, type) and issubclass(event_class, DomainEvent)
        )
        expected_id = (
            validate_event_identity(event_data, row["event_id"], allow_missing=True)
            if domain_payload
            else None
        )

        if event_type in self._event_type_registry:
            event_class = self._event_type_registry[event_type]
            if isinstance(event_class, type) and issubclass(event_class, DomainEvent):
                assert expected_id is not None
                # Plain subclasses historically accept arbitrary attributes.
                # Keep those attributes instead of asking Pydantic to drop them.
                legacy = event_class in (DomainEvent, Event) or (
                    "__dataclass_fields__" not in event_class.__dict__
                )
                if legacy:
                    try:
                        return cast(
                            "_EventType",
                            _checked_domain_event(
                                event_class(
                                    **_restore_legacy_base_fields(
                                        event_data,
                                        has_event_fields=issubclass(event_class, Event),
                                    )
                                ),
                                expected_id,
                            ),
                        )
                    except (ValueError, TypeError) as exc:
                        raise EventStoreError(
                            "Could not restore SQLite event payload"
                        ) from exc
                if is_dataclass(event_class):
                    from pydantic import TypeAdapter

                    try:
                        event = TypeAdapter(event_class).validate_python(event_data)
                        rebuilt = loads(
                            dumps(self.serialize_event(cast("_EventType", event)))
                        )
                        if not _payload_preserved(event_data, rebuilt):
                            raise ValueError("event payload was not preserved")
                    except Exception as exc:  # noqa: BLE001 — validation/serialization failures must not return a partial event
                        raise EventStoreError(
                            "Could not restore SQLite event payload"
                        ) from exc
                    return cast("_EventType", _checked_domain_event(event, expected_id))
            # Preserve the prior constructor contract for registered non-domain classes.
            return cast("_EventType", event_class(**event_data))

        # Fall back to generic DomainEvent; arbitrary event-specific fields
        # remain untyped, but canonical base identity/time are restored.

        # Remove fields that will be set separately to avoid duplicates
        event_data.pop("timestamp", None)
        event_data.pop("id", None)

        timestamp = row["timestamp"]
        if isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp)
            except (ValueError, TypeError) as e:
                logger.debug("Failed to parse timestamp %r: %s", timestamp, e)

        assert expected_id is not None
        event_id = expected_id

        occurred_at = event_data.get("occurred_at", timestamp)
        data = {
            **event_data,
            "id": event_id,
            "timestamp": timestamp,
            "occurred_at": occurred_at,
        }
        data.setdefault("event_id", event_id)
        try:
            return cast(
                "_EventType",
                _checked_domain_event(DomainEvent.from_dict(data), expected_id),
            )
        except (ValueError, TypeError) as exc:
            raise EventStoreError("Could not restore SQLite event payload") from exc


__all__ = ["SqliteEventSerializer"]
