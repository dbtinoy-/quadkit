"""Common type aliases for Quadkit Framework.

All aliases here are defined in terms of standard Python types.  Several
aliases intentionally share the same **underlying** type (``dict[str, Any]``)
but carry distinct **semantic** meaning to make call-sites self-documenting
and to enable targeted mypy type-narrowing in the future.

Alias semantics
---------------
:data:`JSON`
    Arbitrary JSON-serialisable mapping.  Use at I/O boundaries (HTTP bodies,
    cache payloads, event envelopes) where the shape is not yet constrainted by
    a typed schema.

:data:`Metadata`
    Free-form key/value annotations attached to domain objects or context vars.
    Unlike :data:`JSON`, callers may include non-serialisable values (e.g.
    internal bookkeeping objects).

:data:`TokenPayload`
    Claims extracted from a validated JWT / session token.  Always
    ``dict[str, Any]`` because token claim sets are open-world; callers
    immediately destructure the payload into typed fields.

These three aliases are *intentionally* synonymous at the type level.
They exist to make intent visible — prefer the most specific alias at each
call-site.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, TypeAlias
from uuid import UUID

JSON: TypeAlias = dict[str, Any]
Metadata: TypeAlias = dict[str, Any]
TokenPayload: TypeAlias = dict[str, Any]

EntityId: TypeAlias = str | int | UUID
"""Identifier for domain entities — accepts both plain strings, ints, and UUIDs."""

Headers: TypeAlias = dict[str, str]
"""HTTP-style header mapping (header-name → value)."""

QueryParams: TypeAlias = dict[str, str | list[str]]
"""URL query-parameter mapping. Values may be repeated (list) or singular (str)."""

Timestamp: TypeAlias = datetime
"""An unambiguous point in time.  Prefer timezone-aware datetimes."""

Version: TypeAlias = int
"""Optimistic-locking version counter for aggregate roots."""

__all__ = [
    "JSON",
    "EntityId",
    "Headers",
    "Metadata",
    "QueryParams",
    "Timestamp",
    "TokenPayload",
    "Version",
]
