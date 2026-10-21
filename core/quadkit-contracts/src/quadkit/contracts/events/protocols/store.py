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
        from_version: int = 0,
        to_version: int | None = None,
        limit: int | None = None,
    ) -> list[Any]:
        """Read events from a stream.

        Every shipped store -- abstract, in-memory, SQLite, Postgres, MongoDB,
        Redis, outbox and streaming -- declares this exact signature. The
        protocol previously said ``(stream_id, start, count)``; because the
        container only checks member presence, that drift bound cleanly and
        surfaced only as ``type: ignore[call-arg]`` at call sites (S23).
        Widening here is backward compatible: the added parameter is optional,
        so positional and keyword callers both keep working.

        Args:
            stream_id: Unique stream identifier.
            from_version: First version to return; 0 reads from the start.
            to_version: Last version to return, inclusive; ``None`` is unbounded.
            limit: Maximum number of events to return.

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
    """Protocol for aggregate snapshot storage.

    Snapshots are stored as objects, not as loose tuples: every implementation
    in the framework — ``InMemorySnapshotStore`` and the Postgres, SQLite and
    MongoDB stores — exposes ``save_snapshot``/``get_latest``/``get_by_version``/
    ``delete_old_snapshots``, and ``SnapshotManager``, the only consumer, calls
    exactly those.

    This declaration used to be a pre-migration tuple API
    (``save(aggregate_id, snapshot, version)`` / ``load(aggregate_id)``) that no
    implementation ever had. It was not harmless: the container validates
    protocol conformance at registration, so binding a store to this protocol
    failed with ``QK_ERR_DI_007`` — which is why the framework's own
    ``EventsModule`` could export a protocol that could never be resolved, and
    why ``SnapshotManager`` had to silence three attribute errors with
    ``type: ignore``.
    """

    async def save_snapshot(self, snapshot: Any) -> None:
        """Save an aggregate snapshot.

        Args:
            snapshot: Snapshot object carrying the aggregate id, version and
                state. Typed ``Any`` because the snapshot type lives in
                ``quadkit-events`` and contracts must not depend on packages.
        """
        ...

    async def get_latest(self, aggregate_id: str) -> Any | None:
        """Load the latest snapshot for an aggregate.

        Args:
            aggregate_id: Aggregate identifier.

        Returns:
            The newest snapshot, or ``None`` when the aggregate has none.
        """
        ...

    async def get_by_version(
        self, aggregate_id: str | UUID, version: int
    ) -> Any | None:
        """Load one specific snapshot version.

        Args:
            aggregate_id: Aggregate identifier.
            version: Exact snapshot version.

        Returns:
            The snapshot at that version, or ``None``.
        """
        ...

    async def delete_old_snapshots(
        self, aggregate_id: str | UUID, keep_count: int = 3
    ) -> int:
        """Delete superseded snapshots, keeping the newest ``keep_count``.

        Args:
            aggregate_id: Aggregate identifier.
            keep_count: Number of newest snapshots to retain.

        Returns:
            Number of snapshots deleted.
        """
        ...

    async def close(self) -> None:
        """Release the store's resources."""
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
