"""Additional unit tests for events exception classes.

Tests exception hierarchies, code attributes, and edge cases.
"""

import pytest


class TestEventErrorHierarchyExtended:
    """Extended tests for event exception hierarchy."""

    def test_event_error_has_code(self) -> None:
        """Test EventError has _code attribute."""
        from quadkit.contracts.exceptions import EventError

        error = EventError(message="Test error")
        assert hasattr(error, "_code")
        assert error._code.startswith("QK_ERR")

    def test_event_error_details(self) -> None:
        """Test EventError carries details."""
        from quadkit.contracts.exceptions import EventError

        error = EventError(message="Test error", details={"key": "value"})
        assert error.details.get("key") == "value"

    def test_event_error_with_cause(self) -> None:
        """Test EventError handles cause exception."""
        from quadkit.contracts.exceptions import EventError

        cause = ValueError("original error")
        error = EventError(message="Wrapped error", cause=cause)
        assert error.cause is cause


class TestConcurrencyErrorExtended:
    """Extended tests for ConcurrencyError."""

    def test_concurrency_error_code(self) -> None:
        """Test ConcurrencyError has specific code."""
        from quadkit.events.exceptions import ConcurrencyError

        error = ConcurrencyError(expected_version=2, actual_version=1)
        assert error._code == "QK_ERR_EVT_004"

    def test_concurrency_error_details_complete(self) -> None:
        """Test ConcurrencyError includes all version info."""
        from quadkit.events.exceptions import ConcurrencyError

        error = ConcurrencyError(expected_version=5, actual_version=3)
        assert error.details["expected_version"] == 5
        assert error.details["actual_version"] == 3

    def test_concurrency_error_no_versions(self) -> None:
        """Test ConcurrencyError without version info."""
        from quadkit.events.exceptions import ConcurrencyError

        error = ConcurrencyError(message="Lock conflict")
        assert "expected_version" not in error.details
        assert "actual_version" not in error.details


class TestCommandExecutionErrorExtended:
    """Extended tests for CommandExecutionError."""

    def test_command_execution_error_code(self) -> None:
        """Test CommandExecutionError has specific code."""
        from quadkit.events.exceptions import CommandExecutionError

        error = CommandExecutionError(command_type="CreateOrder")
        assert error._code == "QK_ERR_EVT_005"

    def test_command_execution_error_with_error_message(self) -> None:
        """Test CommandExecutionError includes error message."""
        from quadkit.events.exceptions import CommandExecutionError

        error = CommandExecutionError(
            command_type="UpdateInventory",
            error="Validation failed",
        )
        assert error.command_type == "UpdateInventory"
        assert error.error == "Validation failed"


class TestQueryExecutionErrorExtended:
    """Extended tests for QueryExecutionError."""

    def test_query_execution_error_code(self) -> None:
        """Test QueryExecutionError has specific code."""
        from quadkit.events.exceptions import QueryExecutionError

        error = QueryExecutionError(query_type="GetUserByEmail")
        assert error._code == "QK_ERR_EVT_006"

    def test_query_execution_error_with_error_message(self) -> None:
        """Test QueryExecutionError includes error message."""
        from quadkit.events.exceptions import QueryExecutionError

        error = QueryExecutionError(query_type="SearchProducts", error="Timeout")
        assert error.query_type == "SearchProducts"
        assert error.error == "Timeout"


class TestStreamNotFoundErrorExtended:
    """Extended tests for StreamNotFoundError."""

    def test_stream_not_found_error_code(self) -> None:
        """Test StreamNotFoundError has specific code."""
        from quadkit.events.exceptions import StreamNotFoundError

        error = StreamNotFoundError(stream_type="order", stream_id="123")
        assert error._code == "QK_ERR_EVT_007"

    def test_stream_not_found_error_format(self) -> None:
        """Test StreamNotFoundError formats message correctly."""
        from quadkit.events.exceptions import StreamNotFoundError

        error = StreamNotFoundError(stream_type="user", stream_id="abc-123")
        assert error.stream_type == "user"
        assert error.stream_id == "abc-123"
        assert "user" in error.message
        assert "abc-123" in error.message


class TestEventHandlerErrorExtended:
    """Extended tests for EventHandlerError."""

    def test_event_handler_error_code(self) -> None:
        """Test EventHandlerError has specific code."""
        from quadkit.events.exceptions import EventHandlerError

        error = EventHandlerError(
            event_type="UserRegistered",
            handler="send_welcome_email",
            error="SMTP error",
        )
        assert error._code == "QK_ERR_EVT_008"

    def test_event_handler_error_with_cause(self) -> None:
        """Test EventHandlerError includes cause exception."""
        from quadkit.events.exceptions import EventHandlerError

        cause = ConnectionError("SMTP server unreachable")
        error = EventHandlerError(
            event_type="OrderCreated",
            handler="notify_vendor",
            error="Send failed",
            cause=cause,
        )
        assert error.cause is cause


class TestWebhookDeliveryErrorExtended:
    """Extended tests for WebhookDeliveryError."""

    def test_webhook_delivery_error_code(self) -> None:
        """Test WebhookDeliveryError has specific code."""
        from quadkit.events.exceptions import WebhookDeliveryError

        error = WebhookDeliveryError(url="https://api.example.com/hook", status=503)
        assert error._code == "QK_ERR_EVT_018"

    def test_webhook_delivery_error_various_status_codes(self) -> None:
        """Test WebhookDeliveryError handles various HTTP status codes."""
        from quadkit.events.exceptions import WebhookDeliveryError

        for status in [400, 401, 403, 404, 500, 502, 503]:
            error = WebhookDeliveryError(url="https://example.com", status=status)
            assert error.status == status


class TestAggregateNotFoundErrorExtended:
    """Extended tests for AggregateNotFoundError."""

    def test_aggregate_not_found_error_code(self) -> None:
        """Test AggregateNotFoundError has specific code."""
        from quadkit.events.exceptions import AggregateNotFoundError

        error = AggregateNotFoundError()
        assert error._code == "QK_ERR_EVT_009"


class TestEventStoreErrorsExtended:
    """Extended tests for event store exceptions."""

    def test_event_store_error_code(self) -> None:
        """Test EventStoreError has specific code."""
        from quadkit.events.exceptions import EventStoreError

        error = EventStoreError()
        assert error._code == "QK_ERR_EVT_013"

    def test_event_store_connection_error_code(self) -> None:
        """Test EventStoreConnectionError has specific code."""
        from quadkit.events.exceptions import EventStoreConnectionError

        error = EventStoreConnectionError()
        assert error._code == "QK_ERR_EVT_014"


class TestProjectionErrorsExtended:
    """Extended tests for projection exceptions."""

    def test_projection_build_error_code(self) -> None:
        """Test ProjectionBuildError has specific code."""
        from quadkit.events.exceptions import ProjectionBuildError

        error = ProjectionBuildError()
        assert error._code == "QK_ERR_EVT_015"

    def test_projection_rebuild_error_code(self) -> None:
        """Test ProjectionRebuildError has specific code."""
        from quadkit.events.exceptions import ProjectionRebuildError

        error = ProjectionRebuildError()
        assert error._code == "QK_ERR_EVT_016"

    def test_projection_not_found_error_code(self) -> None:
        """Test ProjectionNotFoundError has specific code."""
        from quadkit.events.exceptions import ProjectionNotFoundError

        error = ProjectionNotFoundError()
        assert error._code == "QK_ERR_EVT_017"


class TestFeatureSpecificErrors:
    """Tests for feature-specific exceptions."""

    def test_schema_error_code(self) -> None:
        """Test SchemaError has specific code."""
        from quadkit.events.exceptions import SchemaError

        error = SchemaError()
        assert error._code == "QK_ERR_EVT_019"

    def test_security_error_code(self) -> None:
        """Test SecurityError has specific code."""
        from quadkit.events.exceptions import SecurityError

        error = SecurityError()
        assert error._code == "QK_ERR_EVT_020"

    def test_streaming_error_code(self) -> None:
        """Test StreamingError has specific code."""
        from quadkit.events.exceptions import StreamingError

        error = StreamingError()
        assert error._code == "QK_ERR_EVT_021"

    def test_adapter_connection_error_code(self) -> None:
        """Test AdapterConnectionError has specific code."""
        from quadkit.events.exceptions import AdapterConnectionError

        error = AdapterConnectionError()
        assert error._code == "QK_ERR_EVT_010"

    def test_event_load_error_code(self) -> None:
        """Test EventLoadError has specific code."""
        from quadkit.events.exceptions import EventLoadError

        error = EventLoadError()
        assert error._code == "QK_ERR_EVT_011"

    def test_event_persistence_error_code(self) -> None:
        """Test EventPersistenceError has specific code."""
        from quadkit.events.exceptions import EventPersistenceError

        error = EventPersistenceError()
        assert error._code == "QK_ERR_EVT_012"


class TestExceptionInheritanceValidation:
    """Validate exception inheritance chains."""

    def test_all_event_exceptions_inherit_from_event_error(self) -> None:
        """All custom exceptions inherit from EventError."""
        from quadkit.contracts.exceptions import EventError
        from quadkit.events.exceptions import (
            CommandExecutionError,
            ConcurrencyError,
            EventHandlerError,
            EventLoadError,
            EventPersistenceError,
            EventStoreError,
            EventStoreConnectionError,
            ProjectionBuildError,
            ProjectionRebuildError,
            QueryExecutionError,
            SchemaError,
            SecurityError,
            StreamingError,
            WebhookDeliveryError,
        )

        exceptions = [
            ConcurrencyError,
            CommandExecutionError,
            QueryExecutionError,
            EventHandlerError,
            EventLoadError,
            EventPersistenceError,
            EventStoreError,
            EventStoreConnectionError,
            ProjectionBuildError,
            ProjectionRebuildError,
            QueryExecutionError,
            SchemaError,
            SecurityError,
            StreamingError,
            WebhookDeliveryError,
        ]

        for exc in exceptions:
            assert issubclass(exc, EventError), f"{exc.__name__} should inherit from EventError"

    def test_domain_exceptions_inherit_from_domain_error(self) -> None:
        """Domain exceptions inherit from DomainError."""
        from quadkit.contracts.exceptions import DomainError
        from quadkit.events.exceptions import StreamNotFoundError

        assert issubclass(StreamNotFoundError, DomainError)

    def test_infrastructure_exceptions_inherit_from_infrastructure_error(
        self,
    ) -> None:
        """Infrastructure exceptions inherit from InfrastructureError."""
        from quadkit.contracts.exceptions import InfrastructureError
        from quadkit.events.exceptions import (
            AdapterConnectionError,
            EventPersistenceError,
            EventStoreConnectionError,
        )

        for exc in [AdapterConnectionError, EventPersistenceError, EventStoreConnectionError]:
            assert issubclass(exc, InfrastructureError), f"{exc.__name__} should inherit from InfrastructureError"