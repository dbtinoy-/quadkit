"""Entity base class for entities within aggregates.

Entities are objects with identity that exist within an aggregate boundary.
Unlike aggregates, entities don't have their own event streams.
"""

from __future__ import annotations

from abc import ABC
from datetime import UTC, datetime

from quadkit.domain import Entity as BaseEntity
from quadkit.validation import Field


class Entity(BaseEntity, ABC):
    """Base class for entities within aggregates.

    Entities:
    - Have identity (id field)
    - Are mutable
    - Belong to an aggregate root
    - Don't have their own event streams
    """

    model_config = {"arbitrary_types_allowed": True}  # noqa: RUF012

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime | None = Field(default=None)

    def touch(self) -> None:
        """Update the modified timestamp."""
        self.updated_at = datetime.now(UTC)


class VersionedEntity(Entity):
    """Entity with version tracking.

    Useful for entities that need optimistic concurrency control
    within an aggregate.
    """

    version: int = Field(default=0)

    def increment_version(self) -> None:
        """Increment the entity version."""
        self.version += 1
        self.touch()


__all__ = ["Entity", "VersionedEntity"]
