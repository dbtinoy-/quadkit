"""In-memory implementations for event and snapshot stores.

These implementations are ideal for testing, development, and
single-instance applications.
"""

from __future__ import annotations

from collections import defaultdict
from copy import copy
import dataclasses
from typing import TYPE_CHECKING

from quadkit.contracts.core import HealthCheckResult, HealthStatus
from quadkit.events.exceptions import ConcurrencyError, EventStoreError
from quadkit.events.stores._history import validated_stream_version
from quadkit.events.stores.base import AbstractEventStore, AbstractSnapshotStore

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID

    from quadkit.events.messages.event import Event
    from quadkit.events.schema.evolution import SchemaEvolution
    from quadkit.events.types import Snapshot, StreamInfo


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
        # Absolute versions survive prefix eviction and stream compaction.
        self._stream_versions: dict[str, int] = {}
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
        current_version = self._stream_versions.get(stream_id, 0)
        if not events:
            return current_version
        if expected_version is not None and current_version != expected_version:
            raise ConcurrencyError(
                stream_id=stream_id,
                expected_version=expected_version,
                actual_version=current_version,
            )

        # Prepare the entire batch before touching the stream, global position,
        # or indexes. Constructor-based reconstruction rejects generated frozen
        # dataclasses and can drop dynamic legacy fields; copying preserves both.
        staged: list[tuple[Event, str]] = []
        for i, event in enumerate(events):
            position = self._global_position + i + 1
            version = current_version + i + 1
            try:
                field_names = {f.name for f in dataclasses.fields(event)}
                stamped = copy(event)
                if stamped is event or type(stamped) is not type(event):
                    raise TypeError("event copy is not independent")
                original_dict = getattr(event, "__dict__", None)
                if (
                    original_dict is not None
                    and getattr(stamped, "__dict__", None) is original_dict
                ):
                    raise TypeError("event copy shares attribute storage")
                object.__setattr__(stamped, "sequence_number", position)
                object.__setattr__(stamped, "stream_id", stream_id)
                if "version" in field_names:
                    object.__setattr__(stamped, "version", version)
                if (
                    stamped.sequence_number != position
                    or getattr(stamped, "stream_id", None) != stream_id
                    or ("version" in field_names and stamped.version != version)
                ):
                    raise TypeError("event did not retain stream metadata")
                type_name = str(stamped.event_type)
            except Exception as exc:  # noqa: BLE001 — incompatible events cannot be safely committed
                raise EventStoreError("Could not prepare in-memory event") from exc
            staged.append((stamped, type_name))

        current_stream = self._streams[stream_id]
        for versioned_event, type_name in staged:
            global_idx = len(self._global_log)
            current_stream.append(versioned_event)
            self._global_log.append(versioned_event)
            self._type_index[type_name].append(global_idx)
        self._global_position += len(staged)
        new_version = current_version + len(staged)
        self._stream_versions[stream_id] = new_version

        # Evict oldest events when limit is exceeded (0 = unbounded)
        if self._max_events_per_stream > 0:
            excess = len(current_stream) - self._max_events_per_stream
            if excess > 0:
                current_stream[:] = current_stream[excess:]

        return new_version

    async def read(
        self,
        stream_id: str,
        from_version: int = 0,
        to_version: int | None = None,
        limit: int | None = None,
    ) -> list[Event]:
        """Read events from a stream (M-15)."""

        all_events = self._streams.get(stream_id, [])
        high_water = self._stream_versions.get(stream_id, 0)
        removed_count = high_water - len(all_events)
        start = max(1, from_version)
        if limit == 0 or (to_version is not None and to_version < start):
            return []
        if start <= removed_count:
            raise EventStoreError("In-memory event history was evicted or compacted")

        events = [
            event
            for version, event in enumerate(all_events, start=removed_count + 1)
            if version >= start and (to_version is None or version <= to_version)
        ]

        if limit is not None:
            events = events[:limit]

        # M-03: Apply upcasting
        return await self._apply_upcasting(events)

    async def get_stream_version(self, stream_id: str) -> int:
        """Get the current version of a stream."""
        return self._stream_versions.get(stream_id, 0)

    async def stream_exists(self, stream_id: str) -> bool:
        """Check the logical version, even after full compaction."""
        return await validated_stream_version(self, stream_id) > 0

    async def get_stream_info(self, stream_id: str) -> StreamInfo | None:
        """Report the logical version and metadata of the retained suffix."""
        from quadkit.events.types import StreamInfo

        version = await validated_stream_version(self, stream_id)
        retained = len(self._streams.get(stream_id, []))
        if retained > version:
            raise EventStoreError("In-memory event history is inconsistent")
        if version == 0:
            return None
        missing_prefix = version - retained
        if not retained:
            return StreamInfo(stream_id=stream_id, version=version, event_count=0)

        first = await self.read(stream_id, from_version=missing_prefix + 1, limit=1)
        last = (
            first
            if retained == 1
            else await self.read(stream_id, from_version=version, limit=1)
        )
        if (
            len(first) != 1
            or len(last) != 1
            or await validated_stream_version(self, stream_id) != version
            or len(self._streams.get(stream_id, [])) != retained
        ):
            raise EventStoreError(
                "In-memory event history changed during stream info read"
            )
        return StreamInfo(
            stream_id=stream_id,
            aggregate_type=first[0].aggregate_type,
            version=version,
            event_count=retained,
            created_at=first[0].occurred_at if missing_prefix == 0 else None,
            updated_at=last[0].occurred_at,
        )

    async def get_stream_ids(self) -> list[str]:
        """Get all stream IDs (for testing/debugging)."""
        return list(self._streams.keys())

    async def compact(self, stream_id: str, up_to_version: int) -> int:
        """Purge events for a stream up to (and including) the given version (MF-04)."""
        if stream_id not in self._streams:
            return 0

        events = self._streams[stream_id]
        removed_count = self._stream_versions[stream_id] - len(events)
        remaining = [
            event
            for version, event in enumerate(events, start=removed_count + 1)
            if version > up_to_version
        ]
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
        self._stream_versions.clear()
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
