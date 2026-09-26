"""Schema storage for event versioning."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from quadkit.events.schema.models import EventSchema


class SchemaStore(ABC):
    """Abstract base class for schema storage."""

    @abstractmethod
    async def save(self, schema: EventSchema) -> None:
        """Save a schema."""
        ...

    @abstractmethod
    async def get(self, event_type: str, version: int) -> EventSchema | None:
        """Get a specific schema version."""
        ...

    @abstractmethod
    async def get_latest(self, event_type: str) -> EventSchema | None:
        """Get the latest schema version."""
        ...

    @abstractmethod
    async def get_all_versions(self, event_type: str) -> list[EventSchema]:
        """Get all schema versions for an event type."""
        ...

    @abstractmethod
    async def list_event_types(self) -> list[str]:
        """List all registered event types."""
        ...


class InMemorySchemaStore(SchemaStore):
    """In-memory schema store for development and testing."""

    def __init__(self) -> None:
        """Initialize the in-memory schema store."""
        self._schemas: dict[str, dict[int, EventSchema]] = {}

    async def save(self, schema: EventSchema) -> None:
        """Save a schema."""
        if schema.event_type not in self._schemas:
            self._schemas[schema.event_type] = {}
        self._schemas[schema.event_type][schema.version] = schema

    async def get(self, event_type: str, version: int) -> EventSchema | None:
        """Get a specific schema version."""
        if event_type not in self._schemas:
            return None
        return self._schemas[event_type].get(version)

    async def get_latest(self, event_type: str) -> EventSchema | None:
        """Get the latest schema version."""
        if event_type not in self._schemas:
            return None
        versions = self._schemas[event_type]
        if not versions:
            return None
        latest_version = max(versions.keys())
        return versions[latest_version]

    async def get_all_versions(self, event_type: str) -> list[EventSchema]:
        """Get all schema versions."""
        if event_type not in self._schemas:
            return []
        return sorted(self._schemas[event_type].values(), key=lambda s: s.version)

    async def list_event_types(self) -> list[str]:
        """List all registered event types."""
        return list(self._schemas.keys())
