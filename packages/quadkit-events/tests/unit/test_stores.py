"""Unit tests for quadkit-events stores"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from quadkit.contracts.domain import DomainEvent
from quadkit.events.stores import (
    InMemoryEventStore,
    InMemorySnapshotStore,
    SnapshotManager,
)


class TestInMemoryEventStore:
    """Test InMemoryEventStore"""

    def test_store_creation(self):
        """Test event store creation"""
        store = InMemoryEventStore()
        assert len(store._streams) == 0
        assert store._global_position == 0

    @pytest.mark.asyncio
    async def test_health_check_reports_memory_readiness(self):
        """The offline backend exposes an explicit healthy readiness result."""
        store = InMemoryEventStore()

        result = await store.health_check()

        assert result.is_healthy()
        assert result.component == "InMemoryEventStore"
        assert result.details == {
            "backend": "memory",
            "event_count": 0,
            "stream_count": 0,
        }

    @pytest.mark.asyncio
    async def test_save_events(self):
        """Test saving events"""
        store = InMemoryEventStore()
        aggregate_id = uuid4()

        class TestEvent(DomainEvent):
            value: int

        events = [
            TestEvent(aggregate_id=aggregate_id, sequence_number=1, value=10),
            TestEvent(aggregate_id=aggregate_id, sequence_number=2, value=20),
        ]

        await store.append(str(aggregate_id), events, expected_version=0)

        # Check events were saved
        saved_events = store._streams[str(aggregate_id)]
        print("test debug saved_events dicts", [e.__dict__ for e in saved_events])
        assert len(saved_events) == 2
        print("test debug first event attr list", dir(saved_events[0]))
        print("test debug first event __dict__", saved_events[0].__dict__)
        assert saved_events[0].value == 10
        assert saved_events[1].value == 20

    @pytest.mark.asyncio
    async def test_load_events(self):
        """Test loading events"""
        store = InMemoryEventStore()
        aggregate_id = uuid4()

        class TestEvent(DomainEvent):
            value: int

        events = [
            TestEvent(aggregate_id=aggregate_id, sequence_number=1, value=10),
            TestEvent(aggregate_id=aggregate_id, sequence_number=2, value=20),
        ]

        await store.append(str(aggregate_id), events, expected_version=0)
        loaded_events = await store.read(str(aggregate_id))

        assert len(loaded_events) == 2
        assert loaded_events[0].value == 10
        assert loaded_events[1].value == 20

    @pytest.mark.asyncio
    async def test_load_events_from_version(self):
        """Test loading events from specific version"""
        store = InMemoryEventStore()
        aggregate_id = uuid4()

        class TestEvent(DomainEvent):
            value: int

        events = [
            TestEvent(aggregate_id=aggregate_id, sequence_number=1, value=10),
            TestEvent(aggregate_id=aggregate_id, sequence_number=2, value=20),
            TestEvent(aggregate_id=aggregate_id, sequence_number=3, value=30),
        ]

        await store.append(str(aggregate_id), events, expected_version=0)
        loaded_events = await store.read(str(aggregate_id), from_version=2)

        assert len(loaded_events) == 2
        assert loaded_events[0].value == 20
        assert loaded_events[1].value == 30

    @pytest.mark.asyncio
    async def test_concurrency_check(self):
        """Test concurrency control"""
        store = InMemoryEventStore()
        aggregate_id = uuid4()

        class TestEvent(DomainEvent):
            value: int

        # Save initial event
        events = [TestEvent(aggregate_id=aggregate_id, sequence_number=1, value=10)]
        await store.append(str(aggregate_id), events, expected_version=0)

        # Try to save with wrong expected version
        events2 = [TestEvent(aggregate_id=aggregate_id, sequence_number=2, value=20)]
        with pytest.raises(Exception):  # Should raise concurrency error
            await store.append(str(aggregate_id), events2, expected_version=0)

    @pytest.mark.asyncio
    async def test_stream_all(self):
        """Test streaming all events"""
        store = InMemoryEventStore()
        aggregate_id = uuid4()

        class TestEvent(DomainEvent):
            value: int

        events = [
            TestEvent(aggregate_id=aggregate_id, sequence_number=1, value=10),
            TestEvent(aggregate_id=aggregate_id, sequence_number=2, value=20),
        ]

        await store.append(str(aggregate_id), events, expected_version=0)

        streamed_events = []
        async for event in store.stream_all():
            streamed_events.append(event)

        assert len(streamed_events) == 2
        assert streamed_events[0].value == 10
        assert streamed_events[1].value == 20


class TestInMemorySnapshotStore:
    """Test InMemorySnapshotStore"""

    def test_store_creation(self):
        """Test snapshot store creation"""
        store = InMemorySnapshotStore()
        assert len(store._snapshots) == 0

    @pytest.mark.asyncio
    async def test_save_snapshot(self):
        """Test saving snapshot (M-14)"""
        from quadkit.events.types import Snapshot

        store = InMemorySnapshotStore()
        aggregate_id = uuid4()

        snapshot = Snapshot(
            aggregate_id=aggregate_id,
            aggregate_type="TestAggregate",
            version=5,
            state={"name": "test", "value": 100},
            timestamp=datetime.now(UTC),
        )

        await store.save_snapshot(snapshot)

        # Check snapshot was saved
        saved = await store.get_latest(str(aggregate_id))
        assert saved is not None
        assert saved.version == 5
        assert saved.state["name"] == "test"

    @pytest.mark.asyncio
    async def test_get_latest_snapshot(self):
        """Test getting latest snapshot (M-14)"""
        from quadkit.events.types import Snapshot

        store = InMemorySnapshotStore()
        aggregate_id = uuid4()

        snapshot = Snapshot(
            aggregate_id=aggregate_id,
            aggregate_type="TestAggregate",
            version=5,
            state={"name": "test"},
            timestamp=datetime.now(UTC),
        )
        await store.save_snapshot(snapshot)

        loaded = await store.get_latest(str(aggregate_id))

        assert loaded is not None
        assert loaded.version == 5
        assert loaded.state["name"] == "test"

    @pytest.mark.asyncio
    async def test_get_snapshot_by_version(self):
        """Test getting snapshot by version (M-14)"""
        from quadkit.events.types import Snapshot

        store = InMemorySnapshotStore()
        aggregate_id = uuid4()

        await store.save_snapshot(
            Snapshot(
                aggregate_id=aggregate_id,
                aggregate_type="Test",
                version=1,
                state={"v": 1},
            )
        )
        await store.save_snapshot(
            Snapshot(
                aggregate_id=aggregate_id,
                aggregate_type="Test",
                version=3,
                state={"v": 3},
            )
        )

        loaded = await store.get_by_version(str(aggregate_id), 1)
        assert loaded is not None
        assert loaded.state["v"] == 1

    @pytest.mark.asyncio
    async def test_delete_old_snapshots(self):
        """Test deleting old snapshots (M-14)"""
        from quadkit.events.types import Snapshot

        store = InMemorySnapshotStore()  # Use default max_snapshots (5)
        aggregate_id = uuid4()

        # Save 3 snapshots
        for i in range(3):
            await store.save_snapshot(
                Snapshot(
                    aggregate_id=aggregate_id,
                    aggregate_type="Test",
                    version=i + 1,
                    state={"v": i + 1},
                )
            )

        # Should keep only 2 most recent
        deleted = await store.delete_old_snapshots(str(aggregate_id), keep_count=2)
        assert deleted == 1

        snapshots = store._snapshots[str(aggregate_id)]
        assert len(snapshots) == 2
        # Should keep versions 2 and 3 (most recent)
        versions = [s.version for s in snapshots]
        assert 2 in versions
        assert 3 in versions


class TestSnapshotManager:
    """Test SnapshotManager"""

    def test_manager_creation(self):
        """Test snapshot manager creation"""
        event_store = InMemoryEventStore()
        snapshot_store = InMemorySnapshotStore()
        manager = SnapshotManager(event_store, snapshot_store)
        assert manager._event_store == event_store
        assert manager._snapshot_store == snapshot_store

    @pytest.mark.asyncio
    async def test_load_with_snapshot(self):
        """Test loading with snapshot acceleration"""
        event_store = InMemoryEventStore()
        snapshot_store = InMemorySnapshotStore()
        manager = SnapshotManager(event_store, snapshot_store)

        aggregate_id = uuid4()

        class TestEvent(DomainEvent):
            value: int

        # Create and save initial events to reach version 5
        initial_events = [
            TestEvent(
                aggregate_id=aggregate_id, sequence_number=i + 1, value=(i + 1) * 10
            )
            for i in range(5)
        ]
        await event_store.append(str(aggregate_id), initial_events, expected_version=0)

        # Create and save snapshot (M-14)
        from quadkit.events.types import Snapshot

        snapshot = Snapshot(
            aggregate_id=aggregate_id,
            aggregate_type="TestAggregate",
            version=5,
            state={"name": "test", "value": 100},
            timestamp=datetime.now(UTC),
        )

        await snapshot_store.save_snapshot(snapshot)

        # Create some events after the snapshot
        events = [
            TestEvent(aggregate_id=aggregate_id, sequence_number=6, value=60),
            TestEvent(aggregate_id=aggregate_id, sequence_number=7, value=70),
        ]
        await event_store.append(str(aggregate_id), events, expected_version=5)

        # Load with snapshot
        state_out, replay_events, starting_version = await manager.load_with_snapshot(
            str(aggregate_id),
            "TestAggregate",
        )

        # Manager unpacks state
        assert state_out == {"name": "test", "value": 100}
        assert len(replay_events) == 2
        assert starting_version == 5

    @pytest.mark.asyncio
    async def test_save_and_snapshot(self):
        """Test saving events and creating snapshot"""
        event_store = InMemoryEventStore()
        snapshot_store = InMemorySnapshotStore()
        manager = SnapshotManager(event_store, snapshot_store)

        aggregate_id = uuid4()

        class TestEvent(DomainEvent):
            value: int

        events = [TestEvent(aggregate_id=aggregate_id, sequence_number=1, value=10)]
        current_state = {"name": "test"}

        # Save and force snapshot
        created = await manager.save_and_maybe_snapshot(
            str(aggregate_id),
            "TestAggregate",
            events,
            current_state,
            0,
        )

        # Should not create snapshot (not enough events)
        assert created is False

        # Force create snapshot
        snapshot = await manager.create_snapshot(
            str(aggregate_id),
            "TestAggregate",
            1,
            current_state,
        )

        assert snapshot.aggregate_id == aggregate_id
        assert snapshot.version == 1
        assert snapshot.state == current_state


class TestEventStoreReplay:
    """Verify that replay_events delivers events in per-aggregate causal order."""

    @pytest.mark.asyncio
    async def test_replay_delivers_events_in_aggregate_order(self) -> None:
        """Events for each aggregate are replayed in ascending sequence_number order."""
        store = InMemoryEventStore()

        agg_a = uuid4()
        agg_b = uuid4()

        class TestEvent(DomainEvent):
            value: int

        # Append in interleaved global order:
        # agg_b receives seq 1; agg_a receives seqs 2, 3; agg_b receives seq 4.
        # (InMemoryEventStore assigns sequence_number = global_position)
        await store.append(
            str(agg_b),
            [TestEvent(aggregate_id=agg_b, value=10)],
            expected_version=0,
        )
        await store.append(
            str(agg_a),
            [
                TestEvent(aggregate_id=agg_a, value=1),
                TestEvent(aggregate_id=agg_a, value=2),
            ],
            expected_version=0,
        )
        await store.append(
            str(agg_b),
            [TestEvent(aggregate_id=agg_b, value=20)],
            expected_version=1,
        )

        received: list[DomainEvent] = []

        async def handler(event: DomainEvent) -> None:
            received.append(event)

        count = await store.replay_events(handler)
        assert count == len(received) == 4

        # All events for agg_a must be delivered in ascending sequence_number order
        a_events = [e for e in received if e.aggregate_id == agg_a]
        assert len(a_events) == 2
        seq_a = [e.sequence_number for e in a_events]
        assert seq_a == sorted(seq_a), f"agg_a events not in order: {seq_a}"

        # All events for agg_b must be delivered in ascending sequence_number order
        b_events = [e for e in received if e.aggregate_id == agg_b]
        assert len(b_events) == 2
        seq_b = [e.sequence_number for e in b_events]
        assert seq_b == sorted(seq_b), f"agg_b events not in order: {seq_b}"

    @pytest.mark.asyncio
    async def test_replay_since_filter(self) -> None:
        """Events with occurred_at <= the *since* timestamp are not replayed."""
        store = InMemoryEventStore()
        agg = uuid4()

        class TestEvent(DomainEvent):
            value: int

        # All events share roughly the same timestamp; we craft a cutoff that
        # sits strictly before the current time so at least some events pass.
        cutoff = datetime.now(UTC) - timedelta(seconds=60)

        events = [TestEvent(aggregate_id=agg, value=i) for i in range(4)]
        await store.append(str(agg), events, expected_version=0)

        received: list[DomainEvent] = []

        async def handler(event: DomainEvent) -> None:
            received.append(event)

        await store.replay_events(handler, since=cutoff)
        # All 4 events were created after the cutoff, so all should pass through
        assert len(received) == 4
        for ev in received:
            assert ev.occurred_at > cutoff

    @pytest.mark.asyncio
    async def test_replay_since_excludes_event_at_checkpoint(self) -> None:
        """The exclusive replay checkpoint must not redeliver its boundary event."""
        store = InMemoryEventStore()
        aggregate_id = uuid4()
        cutoff = datetime(2026, 8, 28, 8, 0, 0, tzinfo=UTC)

        class TestEvent(DomainEvent):
            value: int

        await store.append(
            str(aggregate_id),
            [
                TestEvent(aggregate_id=aggregate_id, value=1, occurred_at=cutoff),
                TestEvent(
                    aggregate_id=aggregate_id,
                    value=2,
                    occurred_at=cutoff + timedelta(seconds=1),
                ),
            ],
            expected_version=0,
        )

        received: list[DomainEvent] = []

        async def handler(event: DomainEvent) -> None:
            received.append(event)

        count = await store.replay_events(handler, since=cutoff)

        assert count == 1
        assert [event.value for event in received] == [2]

    @pytest.mark.asyncio
    async def test_replay_returns_zero_on_empty_store(self) -> None:
        """Replaying an empty store returns 0 events handled."""
        store = InMemoryEventStore()

        async def handler(event: DomainEvent) -> None:  # pragma: no cover
            pass

        count = await store.replay_events(handler)
        assert count == 0
