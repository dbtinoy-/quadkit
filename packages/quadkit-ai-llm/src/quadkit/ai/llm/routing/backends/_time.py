"""Shared time helpers for quota backends."""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta

__all__ = ["end_of_utc_day"]


def end_of_utc_day() -> datetime:
    """Return the first instant of the next UTC day.

    Used as the default exhaustion expiry (legacy "rest of today"
    semantics) when ``mark_exhausted`` is called without ``until``.
    """
    tomorrow = datetime.now(UTC).date() + timedelta(days=1)
    return datetime.combine(tomorrow, time.min, tzinfo=UTC)
