"""Unit tests for quadkit-events stores - additional store tests."""

import pytest
from unittest.mock import MagicMock, AsyncMock

from quadkit.events.stores.base import AbstractEventStore, AbstractIdempotencyStore, AbstractSnapshotStore, AbstractCheckpointStore, StoredEvent


class TestInMemoryCheckpointStore:
    """Test InMemoryCheckpointStore class."""

    def test_in_memory_checkpoint_store_creation(self):
        """Test creating an in-memory checkpoint store."""
        from quadkit.events.stores.checkpoints import InMemoryCheckpointStore
        store = InMemoryCheckpointStore()
        assert store is not None

    def test_in_memory_checkpoint_store_has_internal_data(self):
        """Test checkpoint store has internal storage."""
        from quadkit.events.stores.checkpoints import InMemoryCheckpointStore
        store = InMemoryCheckpointStore()
        
        # Store should have some internal state
        assert hasattr(store, '_checkpoints') or hasattr(store, 'checkpoints') or hasattr(store, 'data')


class TestInMemoryIdempotencyStore:
    """Test InMemoryIdempotencyStore class."""

    def test_in_memory_idempotency_store_creation(self):
        """Test creating an in-memory idempotency store."""
        from quadkit.events.stores.idempotency import InMemoryIdempotencyStore
        store = InMemoryIdempotencyStore()
        assert store is not None

    def test_in_memory_idempotency_store_has_internal_data(self):
        """Test idempotency store has internal storage."""
        from quadkit.events.stores.idempotency import InMemoryIdempotencyStore
        store = InMemoryIdempotencyStore()
        
        # Store should have some internal state
        assert hasattr(store, '_entries') or hasattr(store, 'keys') or hasattr(store, 'data')


class TestInMemoryEventStore:
    """Test InMemoryEventStore class."""

    def test_in_memory_event_store_creation(self):
        """Test creating an in-memory event store."""
        from quadkit.events.stores.memory import InMemoryEventStore
        store = InMemoryEventStore()
        assert store is not None


class TestInMemorySnapshotStore:
    """Test InMemorySnapshotStore class."""

    def test_in_memory_snapshot_store_creation(self):
        """Test creating an in-memory snapshot store."""
        from quadkit.events.stores.memory import InMemorySnapshotStore
        store = InMemorySnapshotStore()
        assert store is not None


class TestRedisEventStore:
    """Test RedisEventStore class."""

    def test_redis_event_store_creation(self):
        """Test creating a Redis event store."""
        from quadkit.events.stores.redis import RedisEventStore
        # Mock StateStoreProtocol required by RedisEventStore
        mock_state_store = MagicMock()
        store = RedisEventStore(mock_state_store)
        assert store is not None


class TestOutboxEventStore:
    """Test OutboxEventStore class."""

    def test_outbox_event_store_creation(self):
        """Test creating an outbox event store."""
        from quadkit.events.stores.outbox import OutboxEventStore
        # OutboxEventStore requires inner AbstractEventStore
        mock_inner = MagicMock(spec=AbstractEventStore)
        store = OutboxEventStore(mock_inner)
        assert store is not None


class TestOutboxEntry:
    """Test OutboxEntry class."""

    def test_outbox_entry_creation(self):
        """Test creating an OutboxEntry."""
        from quadkit.events.stores.outbox import OutboxEntry, OutboxEntryStatus
        
        entry = OutboxEntry(
            entry_id="test-id",
            event_type="TestEvent",
            payload='{"test": "data"}',
            metadata='{}',
            status=OutboxEntryStatus.PENDING
        )
        
        assert entry.entry_id == "test-id"
        assert entry.event_type == "TestEvent"


class TestOutboxEntryStatus:
    """Test OutboxEntryStatus enum."""

    def test_outbox_entry_status_values(self):
        """Test OutboxEntryStatus has expected values."""
        from quadkit.events.stores.outbox import OutboxEntryStatus
        
        # Should be a proper enum with values
        assert isinstance(OutboxEntryStatus.PENDING, OutboxEntryStatus)
        assert isinstance(OutboxEntryStatus.PUBLISHED, OutboxEntryStatus)
        assert isinstance(OutboxEntryStatus.FAILED, OutboxEntryStatus)


class TestSqlCheckpointStore:
    """Test SqlCheckpointStore class."""

    def test_sql_checkpoint_store_creation(self):
        """Test creating a SQL checkpoint store."""
        from quadkit.events.stores.checkpoints import SqlCheckpointStore
        # Mock database connection
        mock_connection = MagicMock()
        store = SqlCheckpointStore(mock_connection)
        assert store is not None


class TestAbstractCheckpointStore:
    """Test AbstractCheckpointStore abstract class."""

    def test_abstract_checkpoint_store_is_abc(self):
        """Test that AbstractCheckpointStore is abstract and can't be instantiated."""
        with pytest.raises(TypeError):
            AbstractCheckpointStore()


class TestSqlIdempotencyStore:
    """Test SqlIdempotencyStore class."""

    def test_sql_idempotency_store_can_be_imported(self):
        """Test that SqlIdempotencyStore can be imported."""
        from quadkit.events.stores.idempotency import SqlIdempotencyStore
        assert SqlIdempotencyStore is not None


class TestAbstractIdempotencyStore:
    """Test AbstractIdempotencyStore abstract class."""

    def test_abstract_idempotency_store_is_abc(self):
        """Test that AbstractIdempotencyStore is abstract and can't be instantiated."""
        with pytest.raises(TypeError):
            AbstractIdempotencyStore()


class TestAbstractSnapshotStore:
    """Test AbstractSnapshotStore abstract class."""

    def test_abstract_snapshot_store_is_abc(self):
        """Test that AbstractSnapshotStore is abstract and can't be instantiated."""
        with pytest.raises(TypeError):
            AbstractSnapshotStore()


class TestStoredEvent:
    """Test StoredEvent dataclass."""

    def test_stored_event_creation(self):
        """Test creating a StoredEvent."""
        from datetime import datetime, timezone
        event = StoredEvent(
            global_sequence=1,
            stream_id="test-stream",
            stream_version=1,
            event_id="event-1",
            event_type="TestEvent",
            event_data={"test": "data"},
            metadata={"key": "value"},
            timestamp=datetime.now(timezone.utc)
        )
        
        assert event.stream_id == "test-stream"
        assert event.event_id == "event-1"
        assert event.event_type == "TestEvent"