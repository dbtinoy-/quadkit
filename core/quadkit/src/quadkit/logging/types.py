"""Type definitions for the logging subsystem.

Provides the ``LogLevel`` enum for typed log severity levels.
"""

from __future__ import annotations

from enum import StrEnum


class LogLevel(StrEnum):
    """Canonical log severity levels."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

    @property
    def as_int(self) -> int:
        """Return the stdlib-compatible integer level for this severity."""
        return _LOGLEVEL_TO_INT[self]


# Maps each LogLevel to the corresponding stdlib ``logging`` integer level.
# Single source of truth — imported by processors.py and configurator.py.
_LOGLEVEL_TO_INT: dict[LogLevel, int] = {
    LogLevel.DEBUG: 10,
    LogLevel.INFO: 20,
    LogLevel.WARNING: 30,
    LogLevel.ERROR: 40,
    LogLevel.CRITICAL: 50,
}


__all__ = ["_LOGLEVEL_TO_INT", "LogLevel"]
