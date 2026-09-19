"""Immutable value object base class."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from quadkit.domain.models.base import DomainModel


@dataclass(init=False, frozen=True)
class ValueObject(DomainModel):
    """Immutable value object base class.

    Value objects are defined by their attributes rather than a unique identity.
    Two value objects are considered equal if all their attributes are equal.
    """

    def with_changes(self: Any, **changes: Any) -> Any:
        """Create a new instance with the specified attributes updated."""
        return replace(self, **changes)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, type(self)):
            return NotImplemented
        return self.__dict__ == other.__dict__

    def __hash__(self) -> int:  # type: ignore[override]
        """Hash by field values — consistent with __eq__."""
        return hash(tuple(self.__dict__.items()))
