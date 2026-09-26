"""Base protocols for event stores and snapshot stores.

This module defines the abstract base classes that all event store
and snapshot store implementations must follow.

Stream cursor/iterator methods live in :mod:`quadkit.events.stores._stream`
(:class:`EventStreamMixin`).  Snapshot storage lives in
:mod:`quadkit.events.stores._snapshots` (:class:`AbstractSnapshotStore`).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

# Re-export extracted modules so existing importers keep working.
from quadkit.events.stores._snapshots import (
    AbstractSnapshotStore as AbstractSnapshotStore,
)
from quadkit.events.stores._stream import EventStreamMixin as EventStreamMixin
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from datetime import datetime
    from types import TracebackType
    from uuid import UUID

    from quadkit.events.messages.event import Event
    from quadkit.events.schema.evolution import SchemaEvolution
    from quadkit.events.types import StreamInfo

logger = get_logger(__name__)


@dataclass(frozen=True)
class StoredEvent:
    """Stored event metadata returned by stores."""

    global_sequence: int
    stream_id: str
    stream_version: int
    event_id: Any
    event_type: str
    event_data: dict[str, Any]
    metadata: dict[str, Any] | None
    timestamp: datetime


from quadkit.contracts import EventStoreProtocol as EventStoreProtocol

# ...


class AbstractEventStore(ABC, EventStoreProtocol, EventStreamMixin):
    """Abstract base class for event storage.

    Inherits stream/cursor/replay helpers from :class:`EventStreamMixin`.
    Snapshot storage is provided by :class:`AbstractSnapshotStore`.

    Example::

        # Append events
        await store.append(
            stream_id="order-123",
            events=[OrderCreated(...), ItemAdded(...)],
            expected_version=0
        )

        # Read events
        events = await store.read("order-123")
    """

    def __init__(self, schema_evolution: SchemaEvolution | None = None) -> None:
        """Initialise event store, optionally with schema evolution (M-03)."""
        self._schema_evolution: SchemaEvolution | None = schema_evolution

    @abstractmethod
    async def append(
        self,
        stream_id: str,
        events: list[Event],
        expected_version: int | None = None,
    ) -> int:
        """Append events to a stream with optimistic concurrency.

        Returns:
            New stream version.

        Args:
            stream_id: Unique identifier for the event stream
            events: List of events to save
            expected_version: Expected current version for concurrency control

        Raises:
            ConcurrencyError: If version conflict occurs
            EventPersistenceError: If save operation fails
        """

    @abstractmethod
    async def read(
        self,
        stream_id: str,
        from_version: int = 0,
        to_version: int | None = None,
        limit: int | None = None,
    ) -> list[Event]:
        """Read events from a stream (M-15).

        Args:
            stream_id: Stream to load events from
            from_version: Starting version (inclusive)
            to_version: Ending version (inclusive)
            limit: Max number of events to read

        Returns:
            List of events in chronological order

        Raises:
            EventLoadError: If load operation fails
        """

        # This method is often abstract but we provide a default that raises
        # if not overridden by subclasses.
        raise NotImplementedError

    async def _apply_upcasting(self, events: list[Event]) -> list[Event]:
        """M-03: Upcast events to their latest schema version (no-op if no evolution configured)."""
        if not self._schema_evolution:
            return events
        migrated: list[Any] = []
        for original_event in events:
            event_type = type(original_event).__name__
            latest = await self._schema_evolution.registry.get_latest_version(
                event_type
            )
            current = original_event
            if latest and getattr(original_event, "schema_version", 1) < latest:
                try:
                    current = await self._schema_evolution.migrate_event(
                        original_event, latest
                    )
                except (ValueError, RuntimeError) as exc:
                    logger.warning("Upcasting %s failed: %s", event_type, exc)
            migrated.append(current)
        return migrated

    # Removed load_from_version as read(start=...) covers it

    async def get_stream_version(self, stream_id: str) -> int:
        """Get the current version of a stream.

        Args:
            stream_id: Stream to check

        Returns:
            Current version (0 if stream doesn't exist)
        """
        events = await self.load(stream_id)  # type: ignore[attr-defined]
        return len(events)

    async def stream_exists(self, stream_id: str) -> bool:
        """Check if a stream exists.

        Args:
            stream_id: Stream to check

        Returns:
            True if stream has events
        """
        events = await self.read(stream_id)
        return len(events) > 0

    async def get_stream_info(self, stream_id: str) -> StreamInfo | None:
        """Get information about a stream.

        Args:
            stream_id: Stream to get info for

        Returns:
            StreamInfo or None if stream doesn't exist
        """
        from quadkit.events.types import StreamInfo

        events = await self.read(stream_id)
        if not events:
            return None

        return StreamInfo(
            stream_id=stream_id,
            aggregate_type=events[0].aggregate_type if events else None,
            version=len(events),
            event_count=len(events),
            created_at=events[0].occurred_at if events else None,
            updated_at=events[-1].occurred_at if events else None,
        )

    async def read_all(
        self,
        position: int = 0,
        count: int | None = None,
    ) -> list[Event]:
        """Read all events from the store in global order.

        Default implementation streams from the store's ``stream_all``
        primitive so every backend inherits a working ``read_all`` instead
        of the no-op stub leaked by :class:`EventStoreProtocol`.

        Args:
            position: Starting global sequence number (inclusive).
            count: Maximum number of events to return; ``None`` for all.

        Returns:
            List of events in global order, newest last.
        """
        events: list[Event] = []
        async for event in self.stream_all(
            from_position=position,
            batch_size=count or 100,
        ):
            events.append(event)
            if count is not None and len(events) >= count:
                break
        return events

    @abstractmethod
    def stream_all(
        self,
        from_position: int = 0,
        batch_size: int = 100,
        partition: int | None = None,
        total_partitions: int | None = None,
    ) -> AsyncIterator[Event]:
        """Stream all events from the store in global order.

        Args:
            from_position: Starting global sequence number.
            batch_size: Number of events to fetch per batch.
            partition: Optional partition index (0 to total_partitions - 1).
            total_partitions: Total number of partitions for sharding.
        """
        ...

    @abstractmethod
    async def compact(self, stream_id: str, up_to_version: int) -> int:
        """Purge events for a stream up to (and including) the given version (MF-04).

        Args:
            stream_id: Stream identifier.
            up_to_version: Maximum version to delete.

        Returns:
            Number of events purged.
        """
        ...

    async def find_by_aggregate(
        self,
        aggregate_id: str,
    ) -> list[Event]:
        """Get all events for an aggregate (for reconstitution).

        Args:
            aggregate_id: Aggregate identifier (same as stream_id).

        Returns:
            All events for the aggregate in chronological order.
        """
        return await self.read(aggregate_id)

    @abstractmethod
    async def close(self) -> None:
        """Close the event store and release resources."""
        ...

    async def __aenter__(self) -> AbstractEventStore:
        """Async context manager entry."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Async context manager exit."""
        await self.close()


class AbstractIdempotencyStore(ABC):
    """Abstract interface for message deduplication (M-17)."""

    @abstractmethod
    async def is_processed(self, consumer_id: str, message_id: str | UUID) -> bool:
        """Check if a message has already been processed by a consumer."""

    @abstractmethod
    async def mark_processed(
        self,
        consumer_id: str,
        message_id: str | UUID,
        expires_in: float | None = None,
    ) -> None:
        """Mark a message as processed by a consumer."""

    @abstractmethod
    async def clear_expired(self) -> int:
        """Clear expired idempotency entries."""

    @abstractmethod
    async def close(self) -> None:
        """Close the store and release resources."""

    async def __aenter__(self) -> AbstractIdempotencyStore:
        """Async context manager entry."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Async context manager exit."""
        await self.close()


class AbstractCheckpointStore(ABC):
    """Abstract interface for managing stream checkpoints (MF-03).

    Used by projections and subscribers to track their progress and
    coordinate between instances.
    """

    @abstractmethod
    async def get_checkpoint(self, name: str) -> int:
        """Get the last processed position for a given name."""

    @abstractmethod
    async def save_checkpoint(self, name: str, position: int) -> None:
        """Save the processed position for a given name."""

    @abstractmethod
    async def list_checkpoints(self) -> dict[str, int]:
        """List all saved checkpoints."""

    @abstractmethod
    async def delete_checkpoint(self, name: str) -> None:
        """Delete a checkpoint."""

    @abstractmethod
    async def acquire_lock(self, name: str, owner: str, timeout: float = 30.0) -> bool:
        """Acquire a distributed lock for a given name."""

    @abstractmethod
    async def release_lock(self, name: str, owner: str) -> None:
        """Release a distributed lock."""


class AbstractEventStoreFactory(ABC):
    """Factory for creating event stores."""

    @abstractmethod
    async def create_event_store(self) -> AbstractEventStore:
        """Create and return an event store instance."""


__all__ = [
    "AbstractCheckpointStore",
    "AbstractEventStore",
    "AbstractEventStoreFactory",
    "AbstractIdempotencyStore",
    "AbstractSnapshotStore",
    "EventStreamMixin",
    "StoredEvent",
]
