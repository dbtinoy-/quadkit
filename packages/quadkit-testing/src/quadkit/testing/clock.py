"""Testing clock implementation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from quadkit.contracts.core.clock import Duration

DEFAULT_FIXED_CLOCK_START = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)


def _coerce_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        msg = "FixedClock requires a timezone-aware datetime"
        raise ValueError(msg)
    return value.astimezone(UTC)


def _coerce_seconds(value: float | timedelta | Duration) -> float:
    if isinstance(value, Duration):
        return value.total_seconds
    if isinstance(value, timedelta):
        return value.total_seconds()
    return float(value)


class FixedClock:
    """Deterministic clock for tests."""

    def __init__(self, initial: datetime | None = None) -> None:
        self._now = _coerce_aware_utc(initial or DEFAULT_FIXED_CLOCK_START)
        self._monotonic = 0.0

    def set(self, dt: datetime) -> None:
        """Set the clock to a specific time."""
        self._now = _coerce_aware_utc(dt)
        self._monotonic = 0.0

    def freeze(self, dt: datetime) -> None:
        """Backward-compatible alias for :meth:`set`."""
        self.set(dt)

    def advance(self, delta: float | timedelta | Duration) -> None:
        """Advance the clock by a duration."""
        seconds = _coerce_seconds(delta)
        self._now = self._now + timedelta(seconds=seconds)
        self._monotonic += seconds

    def tick(self) -> None:
        """Advance the clock by one second."""
        self.advance(1.0)

    def now(self) -> datetime:
        """Return the current frozen time."""
        return self._now

    def monotonic(self) -> float:
        """Return elapsed seconds since the clock was created or set."""
        return self._monotonic

    def timestamp(self) -> float:
        """Return the Unix timestamp for the current frozen time."""
        return self._now.timestamp()

    def time(self) -> float:
        """Backward-compatible alias for :meth:`timestamp`."""
        return self.timestamp()


__all__ = ["FixedClock"]
