"""Tests for events DTOs."""

from uuid import uuid4

from quadkit.events.types import SagaState
from quadkit.events.types import (
    Checkpoint,
    EventEnvelope,
    SagaData,
    Snapshot,
    StreamInfo,
)


class TestEventEnvelope:
    """Tests for EventEnvelope."""

    def test_event_envelope_creation(self) -> None:
        """Test creating EventEnvelope."""
        envelope = EventEnvelope(
            stream_id="stream-1",
            event_type="UserCreated",
            event_data={"user_id": "123"},
            version=1,
        )
        assert envelope.stream_id == "stream-1"
        assert envelope.event_type == "UserCreated"
        assert envelope.version == 1
        assert envelope.event_id is not None

    def test_event_envelope_with_metadata(self) -> None:
        """Test EventEnvelope with metadata."""
        envelope = EventEnvelope(
            stream_id="stream-1",
            event_type="UserCreated",
            event_data={},
            version=1,
            correlation_id=uuid4(),
            metadata={"key": "value"},
        )
        assert envelope.correlation_id is not None
        assert envelope.metadata == {"key": "value"}


class TestSnapshot:
    """Tests for Snapshot."""

    def test_snapshot_creation(self) -> None:
        """Test creating Snapshot."""
        snapshot = Snapshot(
            aggregate_id=uuid4(),
            aggregate_type="User",
            version=1,
            state={"name": "John"},
        )
        assert snapshot.aggregate_type == "User"
        assert snapshot.version == 1
        assert snapshot.state == {"name": "John"}


class TestStreamInfo:
    """Tests for StreamInfo."""

    def test_stream_info_creation(self) -> None:
        """Test creating StreamInfo."""
        info = StreamInfo(
            stream_id="stream-1",
            aggregate_type="User",
        )
        assert info.stream_id == "stream-1"
        assert info.aggregate_type == "User"
        assert info.version == 0
        assert info.event_count == 0

    def test_stream_info_with_counts(self) -> None:
        """Test StreamInfo with event counts."""
        info = StreamInfo(
            stream_id="stream-1",
            version=10,
            event_count=100,
        )
        assert info.version == 10
        assert info.event_count == 100


class TestCheckpoint:
    """Tests for Checkpoint."""

    def test_checkpoint_creation(self) -> None:
        """Test creating Checkpoint."""
        checkpoint = Checkpoint(
            projection_name="user_projection",
            stream_position=5,
        )
        assert checkpoint.projection_name == "user_projection"
        assert checkpoint.stream_position == 5
        assert checkpoint.last_processed_event_id is None


class TestSagaData:
    """Tests for SagaData."""

    def test_saga_data_creation(self) -> None:
        """Test creating SagaData."""
        saga = SagaData(
            saga_id=uuid4(),
            saga_type="OrderSaga",
        )
        assert saga.saga_type == "OrderSaga"
        assert saga.state == SagaState.NOT_STARTED
        assert saga.data == {}

    def test_saga_data_with_steps(self) -> None:
        """Test SagaData with steps."""
        saga = SagaData(
            saga_id=uuid4(),
            saga_type="OrderSaga",
            state=SagaState.RUNNING,
            current_step="process_payment",
            completed_steps=["validate_order"],
        )
        assert saga.state == SagaState.RUNNING
        assert saga.current_step == "process_payment"
        assert "validate_order" in saga.completed_steps
