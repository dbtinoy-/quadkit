"""Base class for domain entities with identity."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, TypeVar

from quadkit.domain.models.base import DomainModel

ID = TypeVar("ID")


@dataclass(init=False)
class Entity(DomainModel, Generic[ID]):
    """Base class for domain entities with identity.

    Entities have a distinct identity that persists over time, even if their
    attributes change. Equality is based on the 'id' field.
    """

    id: ID = field(default=None)  # type: ignore[assignment]

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, type(self)):
            return NotImplemented
        return self.id == other.id

    def __hash__(self) -> int:  # type: ignore[override]
        return hash(self.id)

    def __repr__(self) -> str:
        return f"{type(self).__name__}(id={self.id!s})"
