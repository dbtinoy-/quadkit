"""Event store and repository protocols."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any, Protocol, TypeVar, runtime_checkable
from uuid import UUID

TAggregate_co = TypeVar("TAggregate_co", covariant=True)


@runtime_checkable
class EventStoreProtocol(Protocol):
    """Protocol for event store implementations.

    The event store persists and retrieves domain events.

    Example:
        ```python
        class PostgresEventStore:
            async def append(self, stream_id, events, expected_version=None):
                async with self.db.transaction():
                    for event in events:
                        await self.db.insert("events", event.to_dict())
        ```
    """

    async def append(
        self,
        stream_id: str,
        events: list[Any],
        expected_version: int | None = None,
    ) -> int:
        """Append events to a stream.

        Args:
            stream_id: Unique stream identifier.
            events: List of events to append.
            expected_version: Expected stream version for optimistic concurrency.

        Returns:
            New stream version.

        Raises:
            ConcurrencyError: If expected version doesn't match.
        """
        ...

    async def read(
        self,
        stream_id: str,
        start: int = 0,
        count: int | None = None,
    ) -> list[Any]:
        """Read events from a stream.

        Args:
            stream_id: Unique stream identifier.
            start: Starting position.
            count: Maximum events to read.

        Returns:
            List of events.
        """
        ...

    async def read_all(
        self,
        position: int = 0,
        count: int | None = None,
    ) -> list[Any]:
        """Read events from all streams.

        Args:
            position: Starting global position.
            count: Maximum events to read.

        Returns:
            List of events.
        """
        ...


@runtime_checkable
class EventReplayProtocol(Protocol):
    """Optional replay capability for event-store implementations.

    ``EventStoreProtocol`` stays intentionally small so existing append/read
    stores remain compatible.  Stores that can replay their event stream may
    advertise this capability without forcing every custom backend to add a
    no-op method.
    """

    async def replay_events(
        self,
        handler: Callable[[Any], Awaitable[None]],
        since: datetime | None = None,
        event_types: list[str] | None = None,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> int:
        """Replay matching events through an async handler.

        Args:
            since: Optional exclusive timestamp checkpoint; an event at the
                checkpoint is not replayed.

        Returns:
            Number of events successfully delivered to the handler.
        """
        ...


@runtime_checkable
class SnapshotStoreProtocol(Protocol):
    """Protocol for aggregate snapshot storage."""

    async def save(self, aggregate_id: str, snapshot: Any, version: int) -> None:
        """Save an aggregate snapshot.

        Args:
            aggregate_id: Aggregate identifier.
            snapshot: Aggregate state snapshot.
            version: Aggregate version at snapshot.
        """
        ...

    async def load(self, aggregate_id: str) -> tuple[Any, int] | None:
        """Load the latest snapshot.

        Args:
            aggregate_id: Aggregate identifier.

        Returns:
            Tuple of (snapshot, version) or None if not found.
        """
        ...


@runtime_checkable
class EventSourcedReadRepositoryProtocol(Protocol):
    """Protocol for read-only repository access."""

    async def get(self, aggregate_id: UUID | str) -> Any | None:
        """Load an aggregate by ID."""
        ...

    async def exists(self, aggregate_id: UUID | str) -> bool:
        """Check if an aggregate exists."""
        ...

    async def get_all(
        self,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[Any]:
        """Get all aggregates (paginated)."""
        ...


@runtime_checkable
class EventSourcedRepositoryProtocol(EventSourcedReadRepositoryProtocol, Protocol):
    """Protocol for event-sourced repositories (Read/Write)."""

    async def save(self, aggregate: Any) -> None:
        """Save an aggregate."""
        ...


@runtime_checkable
class AggregateFactoryProtocol(Protocol[TAggregate_co]):
    """Factory for creating aggregates."""

    def create(self, aggregate_id: UUID | str) -> TAggregate_co:
        """Create a new aggregate instance.

        Args:
            aggregate_id: Aggregate ID.

        Returns:
            New aggregate instance.
        """
        ...
