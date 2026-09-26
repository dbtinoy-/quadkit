"""In-memory implementations for event and snapshot stores.

These implementations are ideal for testing, development, and
single-instance applications.
"""

from __future__ import annotations

from collections import defaultdict
import dataclasses
from typing import TYPE_CHECKING

from quadkit.contracts.core import HealthCheckResult, HealthStatus
from quadkit.events.exceptions import ConcurrencyError
from quadkit.events.stores.base import AbstractEventStore, AbstractSnapshotStore

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID

    from quadkit.events.messages.event import Event
    from quadkit.events.schema.evolution import SchemaEvolution
    from quadkit.events.types import Snapshot


class InMemoryEventStore(AbstractEventStore):
    """In-memory event store for testing and development.

    M-19: Uses a global log and type index for O(n) and O(matching)
    streaming performance.

    Example::

        store = InMemoryEventStore()

        # Save events
        await store.append(
            stream_id="order-123",
            events=[OrderCreated(...)],
            expected_version=0
        )

        # Load events
        events = await store.read("order-123")
    """

    def __init__(
        self,
        schema_evolution: SchemaEvolution | None = None,
        max_events_per_stream: int = 10000,
    ) -> None:
        """Initialize the in-memory store.

        Args:
            schema_evolution: Optional schema evolution handler.
            max_events_per_stream: Maximum events retained per stream.
                Oldest events are evicted when the limit is exceeded.
                Defaults to 10,000 — set to 0 for unbounded.
        """
        super().__init__(schema_evolution=schema_evolution)
        self._max_events_per_stream = max_events_per_stream
        self._streams: dict[str, list[Event]] = defaultdict(list)
        # M-19: global log maintains insertion order across all streams
        self._global_log: list[Event] = []
        self._global_position: int = 0
        # M-19: type index maps event_type -> list of positions in _global_log
        self._type_index: dict[str, list[int]] = defaultdict(list)

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Report readiness for the process-local in-memory store.

        The in-memory backend has no external dependency to probe.  Reporting
        it explicitly avoids making a configured offline application look
        partially unknown to the EventsProvider health aggregate.
        """
        _ = timeout
        return HealthCheckResult(
            component=self.__class__.__name__,
            status=HealthStatus.HEALTHY,
            details={
                "backend": "memory",
                "event_count": len(self._global_log),
                "stream_count": len(self._streams),
            },
        )

    async def append(
        self,
        stream_id: str,
        events: list[Event],
        expected_version: int | None = None,
    ) -> int:
        """Append events to an in-memory stream with optimistic concurrency.

        Returns:
            New stream version.
        """
        if not events:
            return len(self._streams[stream_id])

        current_stream = self._streams[stream_id]
        current_version = len(current_stream)

        # Optimistic concurrency check
        if expected_version is not None and current_version != expected_version:
            raise ConcurrencyError(
                stream_id=stream_id,
                expected_version=expected_version,
                actual_version=current_version,
            )

        # Assign versions and sequence numbers to new events
        for i, event in enumerate(events):
            version = current_version + i + 1
            self._global_position += 1
            global_idx = len(self._global_log)

            # Create event with version and sequence number.
            # DomainEvent.__init__ may store extra attrs via object.__setattr__
            # (outside the dataclass field registry) — dataclasses.replace() would
            # silently drop those.  We collect ALL instance attributes, overlay
            # the version fields, then reconstruct via the class __init__.
            all_attrs = {
                f.name: getattr(event, f.name) for f in dataclasses.fields(event)
            }
            # Pick up any extra attrs set by DomainEvent.__init__ for non-@dataclass subclasses
            for k, v in vars(event).items():
                if k not in all_attrs:
                    all_attrs[k] = v
            all_attrs["sequence_number"] = self._global_position
            # Stamp the owning stream so partitioned reads
            # (``stream_all(partition=...)``) hash by stream_id, matching the
            # SQL/Redis stores.  Without this the partition filter would fall
            # back to ``str(id(event))`` and scatter events across partitions.
            all_attrs["stream_id"] = stream_id
            if "version" in {f.name for f in dataclasses.fields(event)}:
                all_attrs["version"] = version
            versioned_event = event.__class__(**all_attrs)

            # Update stream, global log, and type index (M-19)
            current_stream.append(versioned_event)
            self._global_log.append(versioned_event)
            self._type_index[str(versioned_event.event_type)].append(global_idx)

        # Evict oldest events when limit is exceeded (0 = unbounded)
        if self._max_events_per_stream > 0:
            excess = len(current_stream) - self._max_events_per_stream
            if excess > 0:
                current_stream[:] = current_stream[excess:]

        return len(current_stream)

    async def read(
        self,
        stream_id: str,
        from_version: int = 0,
        to_version: int | None = None,
        limit: int | None = None,
    ) -> list[Event]:
        """Read events from a stream (M-15)."""

        all_events = self._streams.get(stream_id, [])
        # Stream position is 1-indexed (position = list index + 1).
        # Events may not have a "version" field; use list position as the version.

        # Filter by version range (position in stream, 1-indexed)
        events = [
            e
            for pos, e in enumerate(all_events, start=1)
            if pos >= from_version and (to_version is None or pos <= to_version)
        ]

        if limit is not None:
            events = events[:limit]

        # M-03: Apply upcasting
        return await self._apply_upcasting(events)

    async def get_stream_version(self, stream_id: str) -> int:
        """Get the current version of a stream."""
        return len(self._streams.get(stream_id, []))

    async def get_stream_ids(self) -> list[str]:
        """Get all stream IDs (for testing/debugging)."""
        return list(self._streams.keys())

    async def compact(self, stream_id: str, up_to_version: int) -> int:
        """Purge events for a stream up to (and including) the given version (MF-04)."""
        if stream_id not in self._streams:
            return 0

        events = self._streams[stream_id]
        # Use list position (1-indexed) as the stream version.
        remaining = [e for pos, e in enumerate(events, start=1) if pos > up_to_version]
        deleted_count = len(events) - len(remaining)
        self._streams[stream_id] = remaining

        # Note: We don't necessarily purge from _global_log to avoid sequence gaps
        # but in a real compaction we might. For now, just stream-level compaction.
        return deleted_count

    async def stream_all(
        self,
        from_position: int = 0,
        batch_size: int = 100,
        partition: int | None = None,
        total_partitions: int | None = None,
    ) -> AsyncIterator[Event]:
        """Stream all events across all streams.

        M-19: O(n) from position using _global_log — no merging required.
        """
        _ = batch_size
        import hashlib

        for event in self._global_log:
            if (event.sequence_number or 0) <= from_position:
                continue

            if partition is not None and total_partitions is not None:
                # Stable hash based on stream_id (consistent with SQL implementations)
                stream_id = getattr(event, "stream_id", str(id(event)))
                h = int(
                    hashlib.md5(
                        str(stream_id).encode(), usedforsecurity=False
                    ).hexdigest()[:8],
                    16,
                )
                if h % total_partitions != partition:
                    continue

            yield event

    async def stream_by_type(
        self,
        event_types: list[str],
        from_position: int = 0,
    ) -> AsyncIterator[Event]:
        """Stream events filtered by type.

        M-19: O(matching_events) not O(total_events) using type index.
        """
        # Collect positions from all requested types, sorted
        positions: list[int] = []
        for et in event_types:
            positions.extend(self._type_index.get(et, []))
        positions.sort()

        for idx in positions:
            event = self._global_log[idx]
            if (event.sequence_number or 0) > from_position:
                yield event

    def get_all_streams(self) -> list[str]:
        """Get all stream IDs (for testing/debugging)."""
        return list(self._streams.keys())

    def get_global_position(self) -> int:
        """Get current global position."""
        return self._global_position

    def clear(self) -> None:
        """Clear all events (for testing)."""
        self._streams.clear()
        self._global_log.clear()
        self._global_position = 0
        self._type_index.clear()

    async def close(self) -> None:
        """Close the in-memory event store (no-op)."""
        return


class InMemorySnapshotStore(AbstractSnapshotStore):
    """In-memory snapshot store for testing and development.

    M-14: Uses Snapshot objects throughout (save_snapshot / get_latest /
    get_by_version). The legacy tuple-based save/load methods are provided
    by the AbstractSnapshotStore base class via backward-compat shims.

    Example::

        from quadkit.events.types import Snapshot
        store = InMemorySnapshotStore()

        # Save snapshot
        await store.save_snapshot(Snapshot(
            aggregate_id="order-123",
            aggregate_type="Order",
            version=100,
            state={"status": "completed", "total": 150.00}
        ))

        # Load latest snapshot
        snapshot = await store.get_latest("order-123")
    """

    def __init__(self, max_snapshots_per_aggregate: int = 5) -> None:
        """Initialize the in-memory snapshot store.

        Args:
            max_snapshots_per_aggregate: Maximum snapshots to keep per aggregate
        """
        self._snapshots: dict[str, list[Snapshot]] = defaultdict(list)
        self._max_snapshots = max_snapshots_per_aggregate

    async def save_snapshot(self, snapshot: Snapshot) -> None:
        """Save a snapshot (M-14: accepts Snapshot object)."""
        key = str(snapshot.aggregate_id)
        snapshots = self._snapshots[key]
        snapshots.append(snapshot)
        # Keep most-recent max_snapshots, sorted descending by version
        snapshots.sort(key=lambda s: s.version, reverse=True)
        self._snapshots[key] = snapshots[: self._max_snapshots]

    async def get_latest(self, aggregate_id: str) -> Snapshot | None:
        """Load the latest snapshot for an aggregate."""
        snaps = self._snapshots.get(str(aggregate_id), [])
        return snaps[0] if snaps else None  # already sorted descending

    async def get_by_version(
        self,
        aggregate_id: str | UUID,
        version: int,
    ) -> Snapshot | None:
        """Get the snapshot for a specific version."""
        snaps = self._snapshots.get(str(aggregate_id), [])
        for snap in snaps:
            if snap.version == version:
                return snap
        return None

    async def delete_old_snapshots(
        self,
        aggregate_id: str | UUID,
        keep_count: int = 3,
    ) -> int:
        """Delete old snapshots, keeping only the most recent ones."""
        key = str(aggregate_id)
        snaps = self._snapshots.get(key, [])
        if len(snaps) <= keep_count:
            return 0
        # Already sorted descending
        deleted_count = len(snaps) - keep_count
        self._snapshots[key] = snaps[:keep_count]
        return deleted_count

    def clear(self) -> None:
        """Clear all snapshots (for testing)."""
        self._snapshots.clear()

    async def close(self) -> None:
        """Close the in-memory snapshot store (no-op)."""
        return


__all__ = ["InMemoryEventStore", "InMemorySnapshotStore"]
