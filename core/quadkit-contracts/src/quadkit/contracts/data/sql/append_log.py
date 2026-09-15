"""Append log protocols for event sourcing.

This module defines protocols for append-only event log storage,
used by the event sourcing infrastructure in quadkit-events.
"""

from __future__ import annotations

from typing import Any, Protocol, TypeVar, runtime_checkable

T = TypeVar("T")


@runtime_checkable
class AppendLogProtocol(Protocol[T]):
    """Protocol for append-only event log storage.

    This protocol defines the interface for storing and retrieving
    events in an append-only log structure, typical of event sourcing
    architectures.

    Example:
        ```python
        class PostgresAppendLog:
            def __init__(self, pool):
                self.pool = pool

            async def append(self, stream_id: str, events: list[Event]) -> int:
                async with self.pool.acquire() as conn:
                    # Implementation uses parameterized queries
                    pass

            async def read(self, stream_id: str, from_version: int = 0) -> list[Event]:
                # Read events from a specific stream version
                pass

            async def read_all(self, offset: int = 0, limit: int = 100) -> list[Event]:
                # Read all events with pagination
                pass
        ```
    """

    async def append(
        self,
        stream_id: str,
        events: list[T],
        expected_version: int | None = None,
    ) -> int:
        """Append events to a stream.

        Args:
            stream_id: Unique identifier for the event stream.
            events: List of events to append.
            expected_version: Expected current version for optimistic concurrency.
                If provided and doesn't match, raise ConflictError.

        Returns:
            The new stream version after appending.

        Raises:
            ConflictError: If expected_version doesn't match current version.
        """
        ...

    async def read(
        self,
        stream_id: str,
        from_version: int = 0,
        to_version: int | None = None,
    ) -> list[T]:
        """Read events from a stream.

        Args:
            stream_id: Unique identifier for the event stream.
            from_version: Starting stream version (inclusive).
            to_version: Ending stream version (inclusive). If None, read to end.

        Returns:
            List of events from the stream.
        """
        ...

    async def read_all(self, offset: int = 0, limit: int = 100) -> list[T]:
        """Read all events with pagination.

        Args:
            offset: Number of events to skip.
            limit: Maximum number of events to return.

        Returns:
            List of events.
        """
        ...

    async def get_stream_version(self, stream_id: str) -> int:
        """Get the current version of a stream.

        Args:
            stream_id: Unique identifier for the event stream.

        Returns:
            Current stream version (0 if stream doesn't exist).
        """
        ...

    async def delete_stream(self, stream_id: str) -> bool:
        """Delete all events from a stream.

        Args:
            stream_id: Unique identifier for the event stream.

        Returns:
            True if stream was deleted, False if not found.
        """
        ...

    async def count(self, stream_id: str | None = None) -> int:
        """Count events in a stream or total events.

        Args:
            stream_id: Optional stream ID. If None, count all events.

        Returns:
            Number of events.
        """
        ...


from quadkit.contracts.events.protocols import SnapshotStoreProtocol


@runtime_checkable
class AppendLogSnapshotStore(SnapshotStoreProtocol, Protocol):
    """Protocol for aggregate snapshot storage used by append-log.

    Unlike the event-sourcing snapshot store, this interface includes
    explicit aggregate type and state serialization helpers.  The name has
    been changed to avoid collision with the generic ``SnapshotStoreProtocol`` used
    by the events package.
    """

    async def save_snapshot(
        self,
        aggregate_id: str,
        aggregate_type: str,
        version: int,
        state: dict[str, Any],
    ) -> None:
        """Save an aggregate snapshot.

        Args:
            aggregate_id: Unique identifier for the aggregate.
            aggregate_type: Type of the aggregate.
            version: Snapshot version.
            state: Serialized aggregate state.
        """
        ...

    async def get_snapshot(self, aggregate_id: str) -> dict[str, Any] | None:
        """Get the latest snapshot for an aggregate.

        Args:
            aggregate_id: Unique identifier for the aggregate.

        Returns:
            Snapshot data with version and state, or None if not found.
        """
        ...

    async def delete_snapshots(self, aggregate_id: str) -> int:
        """Delete all snapshots for an aggregate.

        Args:
            aggregate_id: Unique identifier for the aggregate.

        Returns:
            Number of snapshots deleted.
        """
        ...


__all__ = ["AppendLogProtocol", "AppendLogSnapshotStore", "T"]
