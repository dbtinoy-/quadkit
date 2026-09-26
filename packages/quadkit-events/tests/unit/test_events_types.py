"""Unit tests for quadkit-events types (type aliases, dataclasses, and enums)."""

from dataclasses import is_dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from quadkit.events import types as enums  # enums merged into types.py
from quadkit.events import types


class TestTypeAliases:
    """Tests for type aliases defined in types.py."""

    def test_t_type_var(self) -> None:
        """TypeVar T should be defined."""
        assert types.T is not None

    def test_t_command_type_var(self) -> None:
        """TCommand TypeVar bounded to Command should be defined."""
        assert types.TCommand.__bound__ is not None

    def test_t_query_type_var(self) -> None:
        """TQuery TypeVar bounded to Query should be defined."""
        assert types.TQuery.__bound__ is not None

    def test_t_event_type_var(self) -> None:
        """TEvent TypeVar bounded to Event should be defined."""
        assert types.TEvent.__bound__ is not None

    def test_t_result_type_var(self) -> None:
        """TResult TypeVar should be defined."""
        assert types.TResult is not None


class TestMessageTypeEnum:
    """Tests for MessageType enum."""

    def test_command_value(self) -> None:
        assert enums.MessageType.COMMAND == "command"

    def test_query_value(self) -> None:
        assert enums.MessageType.QUERY == "query"

    def test_event_value(self) -> None:
        assert enums.MessageType.EVENT == "event"

    def test_is_str_enum(self) -> None:
        assert isinstance(enums.MessageType.COMMAND, str)


class TestAggregateStatusEnum:
    """Tests for AggregateStatus enum."""

    def test_active_value(self) -> None:
        assert enums.AggregateStatus.ACTIVE == "active"

    def test_deleted_value(self) -> None:
        assert enums.AggregateStatus.DELETED == "deleted"

    def test_archived_value(self) -> None:
        assert enums.AggregateStatus.ARCHIVED == "archived"

    def test_is_str_enum(self) -> None:
        assert isinstance(enums.AggregateStatus.ACTIVE, str)


class TestSagaStateEnum:
    """Tests for SagaState enum."""

    def test_not_started_value(self) -> None:
        assert enums.SagaState.NOT_STARTED == "not_started"

    def test_started_value(self) -> None:
        assert enums.SagaState.STARTED == "started"

    def test_running_value(self) -> None:
        assert enums.SagaState.RUNNING == "running"

    def test_completed_value(self) -> None:
        assert enums.SagaState.COMPLETED == "completed"

    def test_failed_value(self) -> None:
        assert enums.SagaState.FAILED == "failed"

    def test_compensating_value(self) -> None:
        assert enums.SagaState.COMPENSATING == "compensating"

    def test_compensated_value(self) -> None:
        assert enums.SagaState.COMPENSATED == "compensated"

    def test_timed_out_value(self) -> None:
        assert enums.SagaState.TIMED_OUT == "timed_out"

    def test_compensation_failed_value(self) -> None:
        assert enums.SagaState.COMPENSATION_FAILED == "compensation_failed"

    def test_pending_value(self) -> None:
        assert enums.SagaState.PENDING == "pending"

    def test_is_str_enum(self) -> None:
        assert isinstance(enums.SagaState.NOT_STARTED, str)


class TestProjectionStateEnum:
    """Tests for ProjectionState enum."""

    def test_stopped_value(self) -> None:
        assert enums.ProjectionState.STOPPED == "stopped"

    def test_running_value(self) -> None:
        assert enums.ProjectionState.RUNNING == "running"

    def test_catching_up_value(self) -> None:
        assert enums.ProjectionState.CATCHING_UP == "catching_up"

    def test_live_value(self) -> None:
        assert enums.ProjectionState.LIVE == "live"

    def test_faulted_value(self) -> None:
        assert enums.ProjectionState.FAULTED == "faulted"

    def test_rebuilding_value(self) -> None:
        assert enums.ProjectionState.REBUILDING == "rebuilding"


class TestStreamPositionEnum:
    """Tests for StreamPosition enum."""

    def test_start_value(self) -> None:
        assert enums.StreamPosition.START == "start"

    def test_end_value(self) -> None:
        assert enums.StreamPosition.END == "end"

    def test_live_value(self) -> None:
        assert enums.StreamPosition.LIVE == "live"


class TestEventStoreBackendEnum:
    """Tests for EventStoreBackend enum."""

    def test_memory_value(self) -> None:
        assert enums.EventStoreBackend.MEMORY == "memory"

    def test_postgres_value(self) -> None:
        assert enums.EventStoreBackend.POSTGRES == "postgres"

    def test_mongodb_value(self) -> None:
        assert enums.EventStoreBackend.MONGODB == "mongodb"

    def test_sqlite_value(self) -> None:
        assert enums.EventStoreBackend.SQLITE == "sqlite"


class TestSnapshotStrategyEnum:
    """Tests for SnapshotStrategy enum."""

    def test_event_count_value(self) -> None:
        assert enums.SnapshotStrategy.EVENT_COUNT == "event_count"

    def test_time_based_value(self) -> None:
        assert enums.SnapshotStrategy.TIME_BASED == "time_based"

    def test_on_demand_value(self) -> None:
        assert enums.SnapshotStrategy.ON_DEMAND == "on_demand"


class TestEventStatusEnum:
    """Tests for EventStatus enum."""

    def test_pending_value(self) -> None:
        assert enums.EventStatus.PENDING == "pending"

    def test_processed_value(self) -> None:
        assert enums.EventStatus.PROCESSED == "processed"

    def test_failed_value(self) -> None:
        assert enums.EventStatus.FAILED == "failed"


class TestEventSourceEnum:
    """Tests for EventSource enum."""

    def test_user_value(self) -> None:
        assert enums.EventSource.USER == "user"

    def test_system_value(self) -> None:
        assert enums.EventSource.SYSTEM == "system"

    def test_external_value(self) -> None:
        assert enums.EventSource.EXTERNAL == "external"


class TestEventEnvelopeDataclass:
    """Tests for EventEnvelope dataclass."""

    def test_is_dataclass(self) -> None:
        assert is_dataclass(types.EventEnvelope)

    def test_create_with_required_fields(self) -> None:
        env = types.EventEnvelope(
            stream_id="stream-1",
            event_type="TestEvent",
            event_data={"key": "value"},
            version=1,
        )
        assert env.stream_id == "stream-1"
        assert env.event_type == "TestEvent"
        assert env.event_data == {"key": "value"}
        assert env.version == 1
        assert env.event_id is not None

    def test_create_with_optional_fields(self) -> None:
        corr_id = uuid4()
        cau_id = uuid4()
        env = types.EventEnvelope(
            stream_id="stream-1",
            event_type="TestEvent",
            event_data={"key": "value"},
            version=1,
            correlation_id=corr_id,
            causation_id=cau_id,
            metadata={"meta": "data"},
        )
        assert env.correlation_id == corr_id
        assert env.causation_id == cau_id
        assert env.metadata == {"meta": "data"}


class TestSnapshotDataclass:
    """Tests for Snapshot dataclass."""

    def test_is_dataclass(self) -> None:
        assert is_dataclass(types.Snapshot)

    def test_create(self) -> None:
        snap = types.Snapshot(
            aggregate_id=uuid4(),
            aggregate_type="TestAggregate",
            version=1,
            state={"key": "value"},
        )
        assert snap.aggregate_type == "TestAggregate"
        assert snap.version == 1
        assert snap.state == {"key": "value"}


class TestStreamInfoDataclass:
    """Tests for StreamInfo dataclass."""

    def test_is_dataclass(self) -> None:
        assert is_dataclass(types.StreamInfo)

    def test_create_with_defaults(self) -> None:
        info = types.StreamInfo(stream_id="stream-1")
        assert info.stream_id == "stream-1"
        assert info.aggregate_type is None
        assert info.version == 0
        assert info.event_count == 0


class TestCheckpointDataclass:
    """Tests for Checkpoint dataclass."""

    def test_is_dataclass(self) -> None:
        assert is_dataclass(types.Checkpoint)

    def test_create(self) -> None:
        cp = types.Checkpoint(
            projection_name="test_projection",
            stream_position=10,
        )
        assert cp.projection_name == "test_projection"
        assert cp.stream_position == 10


class TestSagaDataDataclass:
    """Tests for SagaData dataclass."""

    def test_is_dataclass(self) -> None:
        assert is_dataclass(types.SagaData)

    def test_create_with_defaults(self) -> None:
        data = types.SagaData(
            saga_id=uuid4(),
            saga_type="TestSaga",
        )
        assert data.saga_type == "TestSaga"
        assert data.state == enums.SagaState.NOT_STARTED
        assert data.current_step is None
        assert data.data == {}
        assert data.completed_steps == []
        assert data.compensated_steps == []


class TestCommandResultDataclass:
    """Tests for CommandResult dataclass."""

    def test_is_dataclass(self) -> None:
        assert is_dataclass(types.CommandResult)

    def test_create_success(self) -> None:
        result = types.CommandResult(
            success=True,
            data={"result": "ok"},
        )
        assert result.success is True
        assert result.data == {"result": "ok"}
        assert result.error is None

    def test_create_failure(self) -> None:
        result = types.CommandResult(
            success=False,
            error="Something went wrong",
        )
        assert result.success is False
        assert result.error == "Something went wrong"


class TestQueryResultDataclass:
    """Tests for QueryResult dataclass."""

    def test_is_dataclass(self) -> None:
        assert is_dataclass(types.QueryResult)

    def test_create_success(self) -> None:
        result = types.QueryResult(
            success=True,
            data={"result": "ok"},
        )
        assert result.success is True
        assert result.data == {"result": "ok"}

    def test_create_cached(self) -> None:
        result = types.QueryResult(
            success=True,
            data={"result": "ok"},
            cached=True,
        )
        assert result.cached is True


class TestHandlerInfoDataclass:
    """Tests for HandlerInfo dataclass."""

    def test_is_dataclass(self) -> None:
        assert is_dataclass(types.HandlerInfo)

    def test_create(self) -> None:
        info = types.HandlerInfo(
            handler_type="command",
            message_type="CreateUser",
            handler_class="CreateUserHandler",
        )
        assert info.handler_type == "command"
        assert info.message_type == "CreateUser"
        assert info.handler_class == "CreateUserHandler"


class TestMiddlewareInfoDataclass:
    """Tests for MiddlewareInfo dataclass."""

    def test_is_dataclass(self) -> None:
        assert is_dataclass(types.MiddlewareInfo)

    def test_create_with_defaults(self) -> None:
        info = types.MiddlewareInfo(
            name="test_middleware",
            order=1,
        )
        assert info.name == "test_middleware"
        assert info.order == 1
        assert info.enabled is True


class TestTypesExports:
    """Tests for __all__ exports from types module."""

    def test_all_contains_expected_items(self) -> None:
        expected = [
            "Checkpoint",
            "CommandResult",
            "EventEnvelope",
            "HandlerInfo",
            "MiddlewareInfo",
            "QueryResult",
            "SagaData",
            "Snapshot",
            "StreamInfo",
        ]
        for item in expected:
            assert item in types.__all__

    def test_all_count(self) -> None:
        assert len(types.__all__) >= 14