"""Identity contracts for the Quadkit framework."""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol, runtime_checkable


class IdStrategy(StrEnum):
    """Available ID generation strategies."""

    UUID4 = "uuid4"
    UUID7 = "uuid7"
    ULID = "ulid"
    PREFIXED = "prefixed"


@runtime_checkable
class IdGeneratorProtocol(Protocol):
    """Injectable identity generator."""

    @property
    def strategy(self) -> IdStrategy:
        """Return the active ID generation strategy."""
        ...

    def generate(self) -> str:
        """Generate a new unique identifier."""
        ...

    def generate_for(self, entity_type: str) -> str:
        """Generate a new identifier for a specific entity type."""
        ...


__all__ = ["IdGeneratorProtocol", "IdStrategy"]
