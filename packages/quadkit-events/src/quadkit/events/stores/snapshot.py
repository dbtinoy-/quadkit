"""Snapshot management with automatic creation policies.

This module provides sophisticated snapshot management including:
- Automatic snapshot creation based on policies
- Snapshot-accelerated event replay
- Snapshot versioning and cleanup
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Generic, TypeVar
from uuid import UUID

from quadkit.events.types import Snapshot, SnapshotStrategy

if TYPE_CHECKING:
    from collections.abc import Callable

    from quadkit.contracts.events import EventStoreProtocol, SnapshotStoreProtocol
    from quadkit.events.config import SnapshotConfig


# Type variable for aggregate state
TState = TypeVar("TState")


class SnapshotPolicy(ABC):
    """Abstract base for snapshot creation policies."""

    @abstractmethod
    def should_snapshot(
        self,
        events_since_snapshot: int,
        last_snapshot_time: datetime | None = None,
        aggregate_version: int = 0,
    ) -> bool:
        """Determine if a snapshot should be created."""
        # Reference unused parameters in the abstract base to satisfy linters.
        _ = last_snapshot_time
        _ = aggregate_version
        raise NotImplementedError


class EventCountPolicy(SnapshotPolicy):
    """Create snapshot after N events."""

    def __init__(self, event_threshold: int = 100):
        self.event_threshold = event_threshold

    def should_snapshot(
        self,
        events_since_snapshot: int,
        last_snapshot_time: datetime | None = None,
        aggregate_version: int = 0,
    ) -> bool:
        # Explicitly reference unused args to satisfy linters
        _ = last_snapshot_time
        _ = aggregate_version
        return events_since_snapshot >= self.event_threshold


class TimeBasedPolicy(SnapshotPolicy):
    """Create snapshot after time interval."""

    def __init__(self, interval_seconds: int = 3600):
        self.interval_seconds = interval_seconds

    def should_snapshot(
        self,
        events_since_snapshot: int,
        last_snapshot_time: datetime | None = None,
        aggregate_version: int = 0,
    ) -> bool:
        # `aggregate_version` is accepted for API compatibility; reference it
        # to satisfy linters when it's not required by this policy.
        _ = aggregate_version

        if last_snapshot_time is None:
            return events_since_snapshot > 0

        elapsed = (datetime.now(UTC) - last_snapshot_time).total_seconds()
        return elapsed >= self.interval_seconds and events_since_snapshot > 0


class CompositePolicy(SnapshotPolicy):
    """Combine multiple policies with AND/OR logic."""

    def __init__(self, policies: list[SnapshotPolicy], require_all: bool = False):
        self.policies = policies
        self.require_all = require_all

    def should_snapshot(
        self,
        events_since_snapshot: int,
        last_snapshot_time: datetime | None = None,
        aggregate_version: int = 0,
    ) -> bool:
        results = [
            p.should_snapshot(
                events_since_snapshot,
                last_snapshot_time,
                aggregate_version,
            )
            for p in self.policies
        ]

        if self.require_all:
            return all(results)
        return any(results)


class SnapshotManager(Generic[TState]):
    """Manages snapshot creation and retrieval for aggregates.

    This is the CRITICAL component that transforms O(N) aggregate loading
    into O(1) by storing and loading snapshots.

    Example:
        ```python
        manager = SnapshotManager(
            event_store=event_store,
            snapshot_store=snapshot_store,
            policy=EventCountPolicy(100)
        )

        # Load aggregate with snapshot acceleration
        state, events = await manager.load_with_snapshot(
            aggregate_id="order-123",
            aggregate_type="Order"
        )

        # Auto-snapshot after save if policy triggers
        await manager.save_and_maybe_snapshot(
            aggregate_id="order-123",
            aggregate_type="Order",
            events=[...],
            current_state=state,
            expected_version=100
        )
        ```
    """

    def __init__(
        self,
        event_store: EventStoreProtocol,
        snapshot_store: SnapshotStoreProtocol,
        policy: SnapshotPolicy | None = None,
        config: SnapshotConfig | None = None,
    ):
        """Initialize the snapshot manager.

        Args:
            event_store: The event store instance
            snapshot_store: The snapshot store instance
            policy: Snapshot creation policy (default: EventCountPolicy(100))
            config: Snapshot configuration
        """
        self._event_store = event_store
        self._snapshot_store = snapshot_store
        self._policy = policy or EventCountPolicy(100)
        # Explicitly construct SnapshotConfig with defaults to satisfy type checker
        if config is None:
            from quadkit.events.config import SnapshotConfig as _SnapshotConfig

            self._config = _SnapshotConfig(
                enabled=True,
                strategy=SnapshotStrategy.EVENT_COUNT,
                event_count_threshold=100,
                time_threshold_seconds=3600,
                max_snapshots_per_aggregate=5,
            )
        else:
            self._config = config

        # Track events since last snapshot per aggregate
        self._events_since_snapshot: dict[str, int] = {}
        self._last_snapshot_time: dict[str, datetime] = {}

    async def load_with_snapshot(
        self,
        aggregate_id: str | UUID,
        aggregate_type: str,
    ) -> tuple[dict[str, Any] | None, list[Any], int]:
        # `aggregate_type` is part of the signature for callers but not used here
        _ = aggregate_type
        """Load aggregate state using snapshot acceleration.

        This is the key method that provides O(1) loading:
        1. Try to load the latest snapshot
        2. Load only events AFTER the snapshot version
        3. Return snapshot state + remaining events

        Returns:
            Tuple of (snapshot_state, events_to_replay, starting_version)
        """
        aggregate_key = str(aggregate_id)

        # Try to get latest snapshot (M-14)
        snapshot = await self._snapshot_store.get_latest(aggregate_key)

        if snapshot:
            state = snapshot.state
            version = snapshot.version
            timestamp = snapshot.timestamp

            # Load only events after snapshot
            events = await self._event_store.read(
                aggregate_key, from_version=version + 1
            )

            # Update tracking
            self._events_since_snapshot[aggregate_key] = len(events)
            if timestamp:
                self._last_snapshot_time[aggregate_key] = timestamp

            return state, events, version

        # No snapshot - load all events
        events = await self._event_store.read(aggregate_key)
        self._events_since_snapshot[aggregate_key] = len(events)

        return None, events, 0

    async def save_and_maybe_snapshot(
        self,
        aggregate_id: str | UUID,
        aggregate_type: str,
        events: list[Any],
        current_state: dict[str, Any],
        expected_version: int,
    ) -> bool:
        """Save events and create snapshot if policy triggers.

        Returns:
            True if a snapshot was created
        """
        aggregate_key = str(aggregate_id)

        # Save events
        await self._event_store.append(aggregate_key, events, expected_version)

        # Update event count
        current_count = self._events_since_snapshot.get(aggregate_key, 0)
        self._events_since_snapshot[aggregate_key] = current_count + len(events)

        # Check if we should snapshot
        events_since = self._events_since_snapshot[aggregate_key]
        last_time = self._last_snapshot_time.get(aggregate_key)
        new_version = expected_version + len(events)

        should_snapshot = self._policy.should_snapshot(
            events_since_snapshot=events_since,
            last_snapshot_time=last_time,
            aggregate_version=new_version,
        )

        if should_snapshot:
            await self.create_snapshot(
                aggregate_id=aggregate_id,
                aggregate_type=aggregate_type,
                version=new_version,
                state=current_state,
            )
            return True

        return False

    async def create_snapshot(
        self,
        aggregate_id: str | UUID,
        aggregate_type: str,
        version: int,
        state: dict[str, Any],
    ) -> Snapshot:
        """Create and store a snapshot."""
        aggregate_key = str(aggregate_id)

        # Ensure aggregate_id is a UUID for Snapshot (raise if invalid)
        if isinstance(aggregate_id, UUID):
            agg_uuid = aggregate_id
        elif self._is_valid_uuid(aggregate_id):
            agg_uuid = UUID(aggregate_id)
        else:
            raise ValueError("Invalid aggregate_id for snapshot")

        # Create payload with metadata
        timestamp = datetime.now(UTC)

        # Create Snapshot DTO (M-14)
        snapshot = Snapshot(
            aggregate_id=agg_uuid,
            aggregate_type=aggregate_type,
            version=version,
            state=state,
            timestamp=timestamp,
        )

        # Save using M-14 API
        await self._snapshot_store.save_snapshot(snapshot)

        # Reset tracking
        self._events_since_snapshot[aggregate_key] = 0
        self._last_snapshot_time[aggregate_key] = timestamp

        return snapshot

    async def force_snapshot(
        self,
        aggregate_id: str | UUID,
        aggregate_type: str,
        state_extractor: Callable[[], dict[str, Any]],
    ) -> Snapshot:
        """Force creation of a snapshot regardless of policy."""
        aggregate_key = str(aggregate_id)

        # Get current version from event store
        events = await self._event_store.read(aggregate_key)
        version = len(events)

        state = state_extractor()

        return await self.create_snapshot(
            aggregate_id=aggregate_id,
            aggregate_type=aggregate_type,
            version=version,
            state=state,
        )

    async def cleanup_old_snapshots(
        self,
        aggregate_id: str | UUID,
        keep_count: int | None = None,
    ) -> int:
        """Clean up old snapshots for an aggregate."""
        count = keep_count or self._config.max_snapshots_per_aggregate
        count_deleted: int = await self._snapshot_store.delete_old_snapshots(
            aggregate_id, count
        )
        return count_deleted

    def _is_valid_uuid(self, value: str) -> bool:
        """Check if a string is a valid UUID."""
        try:
            UUID(value)
        except ValueError:
            return False
        else:
            return True


__all__ = [
    "CompositePolicy",
    "EventCountPolicy",
    "SnapshotManager",
    "SnapshotPolicy",
    "TimeBasedPolicy",
]
