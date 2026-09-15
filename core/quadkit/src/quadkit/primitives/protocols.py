"""Protocols for the core subsystem.

Framework-level building and self-registration contracts used across
builder utilities and registry-keyed classes.
"""

from __future__ import annotations

from typing import Any, ClassVar, Protocol


class Buildable(Protocol):
    """Protocol for types that expose an associated fluent Builder."""

    @classmethod
    def builder(cls) -> Any:
        """Return the Builder instance for this class."""
        ...


class Registrable(Protocol):
    """Protocol for types that carry a well-known registry key."""

    __registry_key__: ClassVar[str]


__all__ = [
    "Buildable",
    "Registrable",
]
