"""Explicit SQL-row datetime serialization for native generated controllers."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from quadkit.contracts.exceptions import SerializationError
from quadkit.serialization.domain import json_serialize


def serialize_sql_row(row: object, *, datetime_fields: Iterable[str]) -> dict[str, Any]:
    """Serialize a SQL row, restoring UTC only on declared datetime fields.

    Native SQL bindings store naive UTC. A raw row is not an HTTP datetime
    representation: restore the timezone before serialization, and normalize
    offset-aware driver values to UTC. Undeclared strings (including nested
    JSON) are never interpreted as timestamps. Missing keys and nullable values
    are preserved; this is not a replacement for entity validation/redaction.

    Args:
        row: Raw repository row or native row entity; never mutated.
        datetime_fields: Explicit entity datetime field names, not user input.

    Returns:
        A JSON-compatible copy with declared timestamps in ISO UTC form.

    Raises:
        SerializationError: The row is not object-shaped, or a declared datetime
            cannot be decoded. This is a server-side storage fault, not request
            validation (the native HTTP filter maps it to a sanitized 500).
    """
    serialized = json_serialize(row)
    if not isinstance(serialized, dict):
        raise SerializationError("SQL row must serialize to an object")
    result = dict(serialized)
    for name in datetime_fields:
        value = result.get(name)
        if value is None:
            continue
        if isinstance(value, str):
            # SQL's space separator and ISO's T are supported. Date-only text
            # is not a stored datetime, even though fromisoformat accepts it.
            if value[10:11] not in {"T", " "}:
                raise SerializationError(f"Invalid SQL datetime field: {name}")
            try:
                value = datetime.fromisoformat(value)
            except ValueError as exc:
                raise SerializationError(f"Invalid SQL datetime field: {name}") from exc
        if not isinstance(value, datetime):
            raise SerializationError(f"Invalid SQL datetime field: {name}")
        value = (
            value.replace(tzinfo=UTC)
            if value.utcoffset() is None
            else value.astimezone(UTC)
        )
        result[name] = value.isoformat()
    return result


__all__ = ["serialize_sql_row"]
