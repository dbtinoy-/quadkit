"""Internal time helpers."""

from __future__ import annotations

from datetime import UTC, datetime


def utcnow() -> datetime:
    """Return an aware UTC datetime representing the current time."""
    return datetime.now(tz=UTC)


__all__ = ["utcnow"]
