"""Abstract snapshot store protocol and base class.

Extracted from ``stores/base.py`` (M-01 split). Snapshot stores optimise
aggregate reconstitution by persisting periodic snapshots, reducing event
replay from O(N) to O(1) + O(events since snapshot).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import TracebackType
    from uuid import UUID

    from quadkit.events.types import Snapshot

__all__ = ["AbstractSnapshotStore"]


class AbstractSnapshotStore(ABC):
    """Abstract base class for snapshot storage.

    Provides optimised aggregate loading by storing periodic snapshots.
    Avoids replaying the entire event history for aggregates with many events.

    Strategy:
        1. Load the latest snapshot (if any).
        2. Load events after the snapshot version.
        3. Apply those events to the snapshot state.

    This reduces loading from O(N) to O(1) + O(events since snapshot).

    Example (M-14 — uses Snapshot object throughout)::

        from quadkit.events.types import Snapshot

        # Save a snapshot
        await store.save(Snapshot(
            aggregate_id=order.id,
            aggregate_type="Order",
            version=order.version,
            state=order.to_dict()
        ))

        # Load the latest snapshot
        snapshot = await store.get_latest("order-123")
        if snapshot:
            order = Order.from_snapshot(snapshot.state)
            events = await event_store.read("order-123", start=snapshot.version)
    """

    # M-14: accept a Snapshot object (preferred API)
    @abstractmethod
    async def save_snapshot(self, snapshot: Snapshot) -> None:
        """Save an aggregate snapshot.

        Args:
            snapshot: Snapshot object containing aggregate_id, version, and state.
        """

    @abstractmethod
    async def get_latest(self, aggregate_id: str) -> Snapshot | None:
        """Load the latest snapshot for an aggregate.

        Args:
            aggregate_id: Aggregate to load snapshot for.

        Returns:
            Snapshot object or None if no snapshot exists.
        """

    @abstractmethod
    async def get_by_version(
        self,
        aggregate_id: str | UUID,
        version: int,
    ) -> Snapshot | None:
        """Get a specific snapshot by version.

        Args:
            aggregate_id: Aggregate identifier.
            version: Exact version to retrieve.

        Returns:
            Snapshot at that version, or None.
        """

    @abstractmethod
    async def delete_old_snapshots(
        self,
        aggregate_id: str | UUID,
        keep_count: int = 3,
    ) -> int:
        """Delete old snapshots, keeping only the most recent ones.

        Args:
            aggregate_id: ID of the aggregate.
            keep_count: Number of snapshots to retain (default: 3).

        Returns:
            Number of snapshots deleted.
        """
        ...

    @abstractmethod
    async def close(self) -> None:
        """Close the snapshot store and release resources."""
        ...

    async def __aenter__(self) -> AbstractSnapshotStore:
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
