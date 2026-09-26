"""Tests for events types enums."""

from quadkit.events.types import (
    AggregateStatus,
    EventSource,
    EventStatus,
    EventStoreBackend,
    MessageType,
    ProjectionState,
    SagaState,
    SnapshotStrategy,
    StreamPosition,
)


class TestMessageType:
    def test_command(self) -> None:
        assert MessageType.COMMAND == "command"

    def test_query(self) -> None:
        assert MessageType.QUERY == "query"

    def test_event(self) -> None:
        assert MessageType.EVENT == "event"


class TestAggregateStatus:
    def test_active(self) -> None:
        assert AggregateStatus.ACTIVE == "active"

    def test_deleted(self) -> None:
        assert AggregateStatus.DELETED == "deleted"

    def test_archived(self) -> None:
        assert AggregateStatus.ARCHIVED == "archived"


class TestSagaState:
    def test_not_started(self) -> None:
        assert SagaState.NOT_STARTED == "not_started"

    def test_started(self) -> None:
        assert SagaState.STARTED == "started"

    def test_running(self) -> None:
        assert SagaState.RUNNING == "running"

    def test_completed(self) -> None:
        assert SagaState.COMPLETED == "completed"

    def test_failed(self) -> None:
        assert SagaState.FAILED == "failed"

    def test_compensating(self) -> None:
        assert SagaState.COMPENSATING == "compensating"

    def test_compensated(self) -> None:
        assert SagaState.COMPENSATED == "compensated"

    def test_timed_out(self) -> None:
        assert SagaState.TIMED_OUT == "timed_out"

    def test_compensation_failed(self) -> None:
        assert SagaState.COMPENSATION_FAILED == "compensation_failed"

    def test_pending(self) -> None:
        assert SagaState.PENDING == "pending"


class TestProjectionState:
    def test_stopped(self) -> None:
        assert ProjectionState.STOPPED == "stopped"

    def test_running(self) -> None:
        assert ProjectionState.RUNNING == "running"

    def test_catching_up(self) -> None:
        assert ProjectionState.CATCHING_UP == "catching_up"

    def test_live(self) -> None:
        assert ProjectionState.LIVE == "live"

    def test_faulted(self) -> None:
        assert ProjectionState.FAULTED == "faulted"

    def test_rebuilding(self) -> None:
        assert ProjectionState.REBUILDING == "rebuilding"


class TestStreamPosition:
    def test_start(self) -> None:
        assert StreamPosition.START == "start"

    def test_end(self) -> None:
        assert StreamPosition.END == "end"

    def test_live(self) -> None:
        assert StreamPosition.LIVE == "live"


class TestEventStoreBackend:
    def test_memory(self) -> None:
        assert EventStoreBackend.MEMORY == "memory"

    def test_postgres(self) -> None:
        assert EventStoreBackend.POSTGRES == "postgres"

    def test_mongodb(self) -> None:
        assert EventStoreBackend.MONGODB == "mongodb"


class TestSnapshotStrategy:
    def test_event_count(self) -> None:
        assert SnapshotStrategy.EVENT_COUNT == "event_count"

    def test_time_based(self) -> None:
        assert SnapshotStrategy.TIME_BASED == "time_based"

    def test_on_demand(self) -> None:
        assert SnapshotStrategy.ON_DEMAND == "on_demand"


class TestEventStatus:
    def test_pending(self) -> None:
        assert EventStatus.PENDING == "pending"

    def test_processed(self) -> None:
        assert EventStatus.PROCESSED == "processed"

    def test_failed(self) -> None:
        assert EventStatus.FAILED == "failed"


class TestEventSource:
    def test_user(self) -> None:
        assert EventSource.USER == "user"

    def test_system(self) -> None:
        assert EventSource.SYSTEM == "system"

    def test_external(self) -> None:
        assert EventSource.EXTERNAL == "external"
