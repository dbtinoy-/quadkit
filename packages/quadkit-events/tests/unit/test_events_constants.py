"""Unit tests for quadkit-events constants."""

import pytest

from quadkit.events import constants as const


class TestVersion:
    """Tests for __version__ constant."""

    def test_version_exists(self) -> None:
        assert const.__version__ is not None
        assert isinstance(const.__version__, str)

    def test_version_is_string(self) -> None:
        assert isinstance(const.__version__, str)


class TestEnvironmentConstants:
    """Tests for environment variable constants."""

    def test_env_prefix(self) -> None:
        assert const.ENV_PREFIX == "QK_EVENTS__"

    def test_env_nested_delimiter(self) -> None:
        assert const.ENV_NESTED_DELIMITER == "__"


class TestHandlerType:
    """Tests for HandlerType StrEnum."""

    def test_command_value(self) -> None:
        assert const.HandlerType.COMMAND.value == "command"

    def test_query_value(self) -> None:
        assert const.HandlerType.QUERY.value == "query"

    def test_event_value(self) -> None:
        assert const.HandlerType.EVENT.value == "event"

    def test_saga_value(self) -> None:
        assert const.HandlerType.SAGA.value == "saga"

    def test_projection_value(self) -> None:
        assert const.HandlerType.PROJECTION.value == "projection"

    def test_is_str_enum(self) -> None:
        assert isinstance(const.HandlerType.COMMAND, str)

    def test_all_values(self) -> None:
        expected = ["command", "query", "event", "saga", "projection"]
        actual = [member.value for member in const.HandlerType]
        assert actual == expected


class TestStoreType:
    """Tests for StoreType StrEnum."""

    def test_memory_value(self) -> None:
        assert const.StoreType.MEMORY.value == "memory"

    def test_postgres_value(self) -> None:
        assert const.StoreType.POSTGRES.value == "postgres"

    def test_mongodb_value(self) -> None:
        assert const.StoreType.MONGODB.value == "mongodb"

    def test_sqlite_value(self) -> None:
        assert const.StoreType.SQLITE.value == "sqlite"

    def test_is_str_enum(self) -> None:
        assert isinstance(const.StoreType.MEMORY, str)


class TestHealthStatus:
    """Tests for HealthStatus StrEnum."""

    def test_healthy_value(self) -> None:
        assert const.HealthStatus.HEALTHY.value == "healthy"

    def test_unhealthy_value(self) -> None:
        assert const.HealthStatus.UNHEALTHY.value == "unhealthy"

    def test_degraded_value(self) -> None:
        assert const.HealthStatus.DEGRADED.value == "degraded"

    def test_unknown_value(self) -> None:
        assert const.HealthStatus.UNKNOWN.value == "unknown"


class TestOperationStatus:
    """Tests for OperationStatus StrEnum."""

    def test_success_value(self) -> None:
        assert const.OperationStatus.SUCCESS.value == "success"

    def test_error_value(self) -> None:
        assert const.OperationStatus.ERROR.value == "error"

    def test_pending_value(self) -> None:
        assert const.OperationStatus.PENDING.value == "pending"

    def test_running_value(self) -> None:
        assert const.OperationStatus.RUNNING.value == "running"

    def test_completed_value(self) -> None:
        assert const.OperationStatus.COMPLETED.value == "completed"

    def test_failed_value(self) -> None:
        assert const.OperationStatus.FAILED.value == "failed"


class TestMessageMetaKey:
    """Tests for MessageMetaKey StrEnum."""

    def test_message_type_value(self) -> None:
        assert const.MessageMetaKey.MESSAGE_TYPE.value == "message_type"

    def test_message_id_value(self) -> None:
        assert const.MessageMetaKey.MESSAGE_ID.value == "message_id"

    def test_timestamp_value(self) -> None:
        assert const.MessageMetaKey.TIMESTAMP.value == "timestamp"

    def test_correlation_id_value(self) -> None:
        assert const.MessageMetaKey.CORRELATION_ID.value == "correlation_id"

    def test_causation_id_value(self) -> None:
        assert const.MessageMetaKey.CAUSATION_ID.value == "causation_id"


class TestTransactionPropagation:
    """Tests for TransactionPropagation StrEnum."""

    def test_required_value(self) -> None:
        assert const.TransactionPropagation.REQUIRED.value == "required"

    def test_requires_new_value(self) -> None:
        assert const.TransactionPropagation.REQUIRES_NEW.value == "requires_new"

    def test_supports_value(self) -> None:
        assert const.TransactionPropagation.SUPPORTS.value == "supports"


class TestWebSocketMessageType:
    """Tests for WebSocketMessageType StrEnum."""

    def test_subscribe_value(self) -> None:
        assert const.WebSocketMessageType.SUBSCRIBE.value == "subscribe"

    def test_unsubscribe_value(self) -> None:
        assert const.WebSocketMessageType.UNSUBSCRIBE.value == "unsubscribe"

    def test_ping_value(self) -> None:
        assert const.WebSocketMessageType.PING.value == "ping"

    def test_pong_value(self) -> None:
        assert const.WebSocketMessageType.PONG.value == "pong"


class TestFilterOperator:
    """Tests for FilterOperator StrEnum."""

    def test_and_value(self) -> None:
        assert const.FilterOperator.AND.value == "and"

    def test_or_value(self) -> None:
        assert const.FilterOperator.OR.value == "or"


class TestSchemaType:
    """Tests for SchemaType StrEnum."""

    def test_string_value(self) -> None:
        assert const.SchemaType.STRING.value == "string"

    def test_integer_value(self) -> None:
        assert const.SchemaType.INTEGER.value == "integer"

    def test_number_value(self) -> None:
        assert const.SchemaType.NUMBER.value == "number"

    def test_boolean_value(self) -> None:
        assert const.SchemaType.BOOLEAN.value == "boolean"

    def test_array_value(self) -> None:
        assert const.SchemaType.ARRAY.value == "array"

    def test_object_value(self) -> None:
        assert const.SchemaType.OBJECT.value == "object"

    def test_null_value(self) -> None:
        assert const.SchemaType.NULL.value == "null"


class TestEnvelopeField:
    """Tests for EnvelopeField StrEnum."""

    def test_event_type_value(self) -> None:
        assert const.EnvelopeField.EVENT_TYPE.value == "event_type"

    def test_timestamp_value(self) -> None:
        assert const.EnvelopeField.TIMESTAMP.value == "timestamp"

    def test_aggregate_id_value(self) -> None:
        assert const.EnvelopeField.AGGREGATE_ID.value == "aggregate_id"

    def test_aggregate_type_value(self) -> None:
        assert const.EnvelopeField.AGGREGATE_TYPE.value == "aggregate_type"

    def test_version_value(self) -> None:
        assert const.EnvelopeField.VERSION.value == "version"

    def test_correlation_id_value(self) -> None:
        assert const.EnvelopeField.CORRELATION_ID.value == "correlation_id"

    def test_causation_id_value(self) -> None:
        assert const.EnvelopeField.CAUSATION_ID.value == "causation_id"

    def test_metadata_value(self) -> None:
        assert const.EnvelopeField.METADATA.value == "metadata"

    def test_event_data_value(self) -> None:
        assert const.EnvelopeField.EVENT_DATA.value == "event_data"


class TestAllExports:
    """Tests for __all__ exports."""

    def test_all_contains_expected_items(self) -> None:
        expected = [
            "ENV_NESTED_DELIMITER",
            "ENV_PREFIX",
            "EnvelopeField",
            "FilterOperator",
            "HandlerType",
            "HealthStatus",
            "MessageMetaKey",
            "OperationStatus",
            "SchemaType",
            "StoreType",
            "TransactionPropagation",
            "WebSocketMessageType",
        ]
        for item in expected:
            assert item in const.__all__, f"{item} not in __all__"

    def test_all_count(self) -> None:
        assert len(const.__all__) == 12