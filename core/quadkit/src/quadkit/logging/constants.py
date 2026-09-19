"""Constants for the logging subsystem."""

from __future__ import annotations

from quadkit.constants import __version__

# -- Log Level Names ---------------------------------------------------------

CRITICAL: str = "critical"
DEBUG: str = "debug"
ERROR: str = "error"
INFO: str = "info"
WARNING: str = "warning"

__all__ = [
    "CRITICAL",
    "DEBUG",
    "ERROR",
    "INFO",
    "WARNING",
    "__version__",
]
