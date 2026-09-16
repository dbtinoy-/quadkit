"""Clock contracts for the Quadkit framework."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import total_ordering
import re
from typing import Protocol, runtime_checkable

_DURATION_PATTERN = re.compile(r"(\d+(?:\.\d+)?)([smhd])", re.IGNORECASE)
_UNIT_TO_SECONDS = {
    "s": 1.0,
    "m": 60.0,
    "h": 3600.0,
    "d": 86400.0,
}


@total_ordering
@dataclass(frozen=True, slots=True)
class Duration:
    """Immutable duration value object.

    The class stores total seconds internally and provides lightweight parsing,
    formatting, and arithmetic helpers for configuration and API boundaries.
    """

    total_seconds: float

    @classmethod
    def seconds(cls, value: float) -> Duration:
        """Create a duration from seconds."""
        return cls(float(value))

    @classmethod
    def minutes(cls, value: float) -> Duration:
        """Create a duration from minutes."""
        return cls(float(value) * 60.0)

    @classmethod
    def hours(cls, value: float) -> Duration:
        """Create a duration from hours."""
        return cls(float(value) * 3600.0)

    @classmethod
    def days(cls, value: float) -> Duration:
        """Create a duration from days."""
        return cls(float(value) * 86400.0)

    @classmethod
    def zero(cls) -> Duration:
        """Create a zero duration."""
        return cls(0.0)

    @classmethod
    def parse(cls, value: str) -> Duration:
        """Parse a human-readable duration string.

        Supported units are seconds (``s``), minutes (``m``), hours (``h``),
        and days (``d``). Chained forms like ``1h30m`` are supported.
        """
        normalized = value.strip().lower()
        if not normalized:
            msg = "Duration string cannot be empty"
            raise ValueError(msg)

        matches = list(_DURATION_PATTERN.finditer(normalized))
        if not matches or "".join(match.group(0) for match in matches) != normalized:
            msg = f"Invalid duration string: {value!r}"
            raise ValueError(msg)

        total = 0.0
        for match in matches:
            amount = float(match.group(1))
            unit = match.group(2).lower()
            total += amount * _UNIT_TO_SECONDS[unit]
        return cls(total)

    @property
    def seconds_value(self) -> float:
        """Backward-compatible alias for the total seconds."""
        return self.total_seconds

    def to_timedelta(self) -> timedelta:
        """Convert the duration to :class:`datetime.timedelta`."""
        return timedelta(seconds=self.total_seconds)

    def __add__(self, other: Duration) -> Duration:
        return Duration(self.total_seconds + other.total_seconds)

    def __sub__(self, other: Duration) -> Duration:
        return Duration(self.total_seconds - other.total_seconds)

    def __mul__(self, factor: float) -> Duration:
        return Duration(self.total_seconds * float(factor))

    def __rmul__(self, factor: float) -> Duration:
        return self * factor

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Duration):
            return NotImplemented
        return self.total_seconds == other.total_seconds

    def __hash__(self) -> int:
        return hash(self.total_seconds)

    def __lt__(self, other: Duration) -> bool:
        if not isinstance(other, Duration):
            return NotImplemented
        return self.total_seconds < other.total_seconds

    def __bool__(self) -> bool:
        return self.total_seconds != 0.0

    def __str__(self) -> str:
        total = self.total_seconds
        if total == 0:
            return "0s"

        remaining = abs(total)
        parts: list[str] = []
        for suffix, unit_seconds in (("d", 86400.0), ("h", 3600.0), ("m", 60.0)):
            amount = int(remaining // unit_seconds)
            if amount:
                parts.append(f"{amount}{suffix}")
                remaining -= amount * unit_seconds
        if remaining:
            if remaining.is_integer():
                parts.append(f"{int(remaining)}s")
            else:
                parts.append(f"{remaining:g}s")

        rendered = "".join(parts) or "0s"
        return f"-{rendered}" if total < 0 else rendered


@runtime_checkable
class ClockProtocol(Protocol):
    """Injectable time source for the framework."""

    def now(self) -> datetime:
        """Return the current timezone-aware UTC time."""
        ...

    def monotonic(self) -> float:
        """Return a monotonic elapsed-time counter."""
        ...

    def timestamp(self) -> float:
        """Return the current Unix timestamp in UTC seconds."""
        ...

    def time(self) -> float:
        """Backward-compatible alias for :meth:`timestamp`."""
        ...


__all__ = ["ClockProtocol", "Duration"]
