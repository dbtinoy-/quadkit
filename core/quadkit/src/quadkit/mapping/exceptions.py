"""Exceptions for the mapping subsystem.

Provides a typed exception hierarchy for mapper registration failures
and mapping execution errors.
"""

from __future__ import annotations

from quadkit.contracts.exceptions import QuadkitError


class MappingError(QuadkitError):
    """Base exception for all object-mapping errors."""

    _code: str = "QK_ERR_MAP_002"


class MappingNotFoundError(MappingError):
    """Raised when no mapper is registered for a (source, destination) type pair."""

    _code: str = "QK_ERR_MAP_003"

    def __init__(self, source: type, dest: type) -> None:
        super().__init__(
            f"No mapper registered from {source.__name__!r} to {dest.__name__!r}"
        )
        self.source = source
        self.dest = dest


class MappingExecutionError(MappingError):
    """Raised when a registered mapper raises an unexpected error during execution."""

    _code: str = "QK_ERR_MAP_004"


__all__ = [
    "MappingError",
    "MappingExecutionError",
    "MappingNotFoundError",
]
