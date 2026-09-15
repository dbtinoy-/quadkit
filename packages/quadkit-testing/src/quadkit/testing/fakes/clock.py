"""Clock protocol and fake/real implementations for deterministic testing."""

from __future__ import annotations

from datetime import UTC, datetime
import time
from typing import Protocol, runtime_checkable

__all__ = [
    "Clock",
    "FakeClock",
    "SystemClock",
]


@runtime_checkable
class Clock(Protocol):
    """Protocol for time sources — allows swapping real/fake clocks."""

    def now(self) -> datetime: ...

    def monotonic(self) -> float: ...

    def time(self) -> float: ...


class SystemClock:
    """Real system clock satisfying the :class:`Clock` protocol."""

    def now(self) -> datetime:
        """Return the current UTC time."""
        return datetime.now(UTC)

    def monotonic(self) -> float:
        """Return the monotonic clock value."""
        return time.monotonic()

    def time(self) -> float:
        """Return the current Unix timestamp."""
        return time.time()


class FakeClock:
    """Controllable clock for deterministic time-based testing.

    Example::

        clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
        assert clock.now().year == 2026
        clock.advance(3600)
        assert clock.now().hour == 1
    """

    def __init__(self, now: datetime | None = None) -> None:
        self._base_time = now or datetime.now(UTC)
        self._base_monotonic = 0.0
        self._offset_seconds = 0.0

    def now(self) -> datetime:
        """Return the current fake time."""
        from datetime import timedelta

        return self._base_time + timedelta(seconds=self._offset_seconds)

    def monotonic(self) -> float:
        """Return a monotonic counter (starts at 0)."""
        return self._base_monotonic + self._offset_seconds

    def time(self) -> float:
        """Return Unix timestamp of the current fake time."""
        return self.now().timestamp()

    def advance(self, seconds: float) -> None:
        """Move time forward by *seconds*."""
        self._offset_seconds += seconds

    def freeze(self, at: datetime) -> None:
        """Set the clock to a specific point in time."""
        self._base_time = at
        self._offset_seconds = 0.0

    def tick(self) -> None:
        """Advance by exactly 1 second."""
        self.advance(1.0)
