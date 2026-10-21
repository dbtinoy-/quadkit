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

The helper is deliberately stdlib-only: ``quadkit-contracts`` is the bottom of
the dependency order (``quadkit-contracts`` ← ``quadkit`` ← extensions) and must
not import a serializer from above it.
"""

from __future__ import annotations

import json
from typing import Any

__all__ = ["encode_bind_value", "encode_bind_values"]


def encode_bind_value(value: Any) -> Any:
    """Return *value* in the form a relational driver can bind.

    ``dict`` and ``list`` values are encoded to compact JSON text, which is
    what a ``JSONB``/``TEXT`` column stores and what the framework's stores
    read back and decode. Every other value passes through untouched, so a
    provider can call this unconditionally on its parameter list.

    Args:
        value: Value about to be bound to a driver parameter.

    Returns:
        The value unchanged, or its compact JSON text when it is a ``dict``
        or ``list``.

    Example:
        >>> encode_bind_value({"order_id": "7"})
        '{"order_id":"7"}'
        >>> encode_bind_value("plain")
        'plain'
    """
    if isinstance(value, (dict, list)):
        return json.dumps(value, separators=(",", ":"), default=str)
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
