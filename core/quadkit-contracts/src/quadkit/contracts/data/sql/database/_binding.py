"""Bind-value encoding shared by every ``DatabaseProviderProtocol`` implementation.

Relational drivers bind scalars, not Python containers: passing a ``dict`` or
``list`` as a parameter raises at the driver (``sqlite3.ProgrammingError: type
'dict' is not supported``, asyncpg's ``DataError``) before the statement runs.
The framework's own stores write JSON-shaped payloads through the provider-level
CRUD surface all the same — an inbox message's ``metadata``, a delivery
record's ``message``, a task's ``payload`` — into columns declared
``JSONB``/``TEXT``, so *encoding those values is part of the contract*, not an
implementation detail each provider re-derives.

This module is where that rule lives so it has exactly one implementation:
``quadkit-sql``'s reference providers encode with :func:`encode_bind_value`,
implementations outside that package use the same function instead of writing
their own, and the compliance suite asserts the behaviour every provider must
show.

Timestamps are the other value the raw-SQL path has to canonicalise. The
framework stores *naive UTC* everywhere — the ORM types normalise aware values
on bind, and the PostgreSQL engine rejects an aware datetime outright
(``can't subtract offset-naive and offset-aware datetimes``). A statement built
as text has no column type to normalise through, so an aware datetime reached
the driver as-is and SQLite wrote ``2026-01-01 09:00:00+00:00`` where the ORM
would have written ``2026-01-01 09:00:00``. Both parse, but only one compares
lexicographically against a stored naive value, which is how a windowed read
silently returned nothing. The conversion therefore belongs here, next to the
JSON rule, for the same reason: one implementation, applied unconditionally by
every provider.

The helper is deliberately stdlib-only: ``quadkit-contracts`` is the bottom of
the dependency order (``quadkit-contracts`` ← ``quadkit`` ← extensions) and must
not import a serializer from above it.
"""

from __future__ import annotations

from datetime import UTC, datetime
import json
from typing import Any

__all__ = ["encode_bind_value", "encode_bind_values"]


def encode_bind_value(value: Any) -> Any:
    """Return *value* in the form a relational driver can bind.

    ``dict`` and ``list`` values are encoded to compact JSON text, which is
    what a ``JSONB``/``TEXT`` column stores and what the framework's stores
    read back and decode. Aware datetimes become naive UTC; other values
    pass through untouched. Providers call this unconditionally on parameters.

    Args:
        value: Value about to be bound to a driver parameter.

    Returns:
        Compact JSON text for a ``dict`` or ``list``, naive UTC for an aware
        datetime, or the unchanged value otherwise.

    Example:
        >>> encode_bind_value({"order_id": "7"})
        '{"order_id":"7"}'
        >>> encode_bind_value("plain")
        'plain'
    """
    if isinstance(value, (dict, list)):
        return json.dumps(value, separators=(",", ":"), default=str)
    if isinstance(value, datetime) and value.tzinfo is not None:
        # Stored timestamps are naive UTC (see the module docstring): normalise
        # here so a text statement writes the same value the ORM mapping would.
        return value.astimezone(UTC).replace(tzinfo=None)
    return value


def encode_bind_values(values: Any) -> list[Any]:
    """Encode every element of *values* for driver binding.

    Convenience wrapper for a positional parameter list.

    Args:
        values: Positional parameters about to be bound.

    Returns:
        A new list with each JSON-shaped element encoded.
    """
    return [encode_bind_value(value) for value in values or []]
