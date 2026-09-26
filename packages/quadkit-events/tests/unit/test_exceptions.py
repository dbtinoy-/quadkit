"""Tests for events exceptions."""

import pytest

from quadkit.events.exceptions import (
    AdapterConnectionError,
    AggregateNotFoundError,
    CommandExecutionError,
    ConcurrencyError,
    EventError,
    EventHandlerError,
    EventLoadError,
    EventPersistenceError,
    EventStoreConnectionError,
    EventStoreError,
    ProjectionBuildError,
    ProjectionNotFoundError,
    ProjectionRebuildError,
    QueryExecutionError,
    SchemaError,
    SecurityError,
    StreamNotFoundError,
    StreamingError,
    WebhookDeliveryError,
)


class TestCommandExecutionError:
    """Tests for CommandExecutionError."""

    def test_default_message(self) -> None:
        """Test default message."""
        err = CommandExecutionError()
        assert err.message == "Command execution failed"
        assert err.command_type is None
        assert err.error is None

    def test_with_command_type(self) -> None:
        """Test with command type."""
        err = CommandExecutionError(command_type="CreateOrder")
        assert err.command_type == "CreateOrder"

    def test_with_error(self) -> None:
        """Test with error."""
        err = CommandExecutionError(error="Database connection failed")
        assert err.error == "Database connection failed"


class TestQueryExecutionError:
    """Tests for QueryExecutionError."""

    def test_default_message(self) -> None:
        """Test default message."""
        err = QueryExecutionError()
        assert err.message == "Query execution failed"
        assert err.query_type is None
        assert err.error is None

    def test_with_query_type(self) -> None:
        """Test with query type."""
        err = QueryExecutionError(query_type="GetUser")
        assert err.query_type == "GetUser"


class TestConcurrencyError:
    """Tests for ConcurrencyError."""

    def test_default_message(self) -> None:
        """Test default message."""
        err = ConcurrencyError()
        assert err.message == "Concurrency error"
        assert err._code == "QK_ERR_EVT_004"

    def test_with_versions(self) -> None:
        """Test with version info."""
        err = ConcurrencyError(expected_version=5, actual_version=3)
        # Version info is passed to parent but not stored as direct attributes
        assert err._code == "QK_ERR_EVT_004"


class TestStreamNotFoundError:
    """Tests for StreamNotFoundError."""

    def test_with_stream_type_and_id(self) -> None:
        """Test with stream type and id."""
        err = StreamNotFoundError("Order", "order-123")
        assert err.stream_type == "Order"
        assert err.stream_id == "order-123"
        assert "Order" in err.message
        assert "order-123" in err.message

    def test_custom_message(self) -> None:
        """Test custom message."""
        err = StreamNotFoundError("Order", "order-123", message="Custom error")
        assert err.message == "Custom error"


class TestEventHandlerError:
    """Tests for EventHandlerError."""

    def test_with_all_params(self) -> None:
        """Test with all parameters."""
        err = EventHandlerError(
            event_type="OrderCreated",
            handler="OrderHandler",
            error="Database error",
        )
        assert err.event_type == "OrderCreated"
        assert err.handler == "OrderHandler"
        assert err.error == "Database error"


class TestWebhookDeliveryError:
    """Tests for WebhookDeliveryError."""

    def test_with_url_and_status(self) -> None:
        """Test with URL and status."""
        err = WebhookDeliveryError(url="https://example.com/webhook", status=500)
        assert err.url == "https://example.com/webhook"
        assert err.status == 500

    def test_default_message(self) -> None:
        """Test default message."""
        err = WebhookDeliveryError(url="https://example.com/webhook", status=500)
        assert err.message == "Webhook delivery failed"


class TestEventLoadError:
    """Tests for EventLoadError."""

    def test_default_code(self) -> None:
        """Test default code."""
        err = EventLoadError()
        assert err._code == "QK_ERR_EVT_011"


class TestEventStoreError:
    """Tests for EventStoreError."""

    def test_default_code(self) -> None:
        """Test default code."""
        err = EventStoreError()
        assert err._code == "QK_ERR_EVT_013"


class TestEventStoreConnectionError:
    """Tests for EventStoreConnectionError."""

    def test_default_code(self) -> None:
        """Test default code is infrastructure error."""
        err = EventStoreConnectionError()
        assert err._code == "QK_ERR_EVT_014"


class TestSimpleAliases:
    """Tests for simple alias exceptions."""

    def test_adapter_connection_error(self) -> None:
        """Test AdapterConnectionError can be instantiated."""
        err = AdapterConnectionError("Connection failed")
        assert err.message == "Connection failed"

    def test_aggregate_not_found_error(self) -> None:
        """Test AggregateNotFoundError can be instantiated."""
        err = AggregateNotFoundError("Aggregate not found")
        assert err.message == "Aggregate not found"

    def test_projection_build_error(self) -> None:
        """Test ProjectionBuildError can be instantiated."""
        err = ProjectionBuildError("ProjectionProtocol build failed")
        assert err.message == "ProjectionProtocol build failed"

    def test_projection_rebuild_error(self) -> None:
        """Test ProjectionRebuildError can be instantiated."""
        err = ProjectionRebuildError("ProjectionProtocol rebuild failed")
        assert err.message == "ProjectionProtocol rebuild failed"

    def test_projection_not_found_error(self) -> None:
        """Test ProjectionNotFoundError can be instantiated."""
        err = ProjectionNotFoundError("ProjectionProtocol not found")
        assert err.message == "ProjectionProtocol not found"

    def test_event_persistence_error(self) -> None:
        """Test EventPersistenceError can be instantiated."""
        err = EventPersistenceError("Persistence failed")
        assert err.message == "Persistence failed"

    def test_event_error(self) -> None:
        """Test EventError can be instantiated."""
        err = EventError("Generic event error")
        assert err.message == "Generic event error"

    def test_schema_error(self) -> None:
        """Test SchemaError can be instantiated."""
        err = SchemaError("Schema error")
        assert err.message == "Schema error"

    def test_security_error(self) -> None:
        """Test SecurityError can be instantiated."""
        err = SecurityError("Security error")
        assert err.message == "Security error"

    def test_streaming_error(self) -> None:
        """Test StreamingError can be instantiated."""
        err = StreamingError("Streaming error")
        assert err.message == "Streaming error"
