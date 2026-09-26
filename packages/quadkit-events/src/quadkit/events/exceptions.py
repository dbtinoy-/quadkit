"""Exception hierarchy for quadkit-events.

All exceptions organized by inheritance level:
1. Re-exports from quadkit.contracts (base classes)
2. CQRS-level exceptions (ConcurrencyError, CommandExecutionError, QueryExecutionError)
3. Domain-level exceptions (AggregateNotFoundError, StreamNotFoundError)
4. Infrastructure-level exceptions (EventStoreError, EventStoreConnectionError)
5. Feature-specific exceptions (ProjectionError, WebhookDeliveryError, SchemaError, etc.)
"""

from __future__ import annotations

from typing import Any

from quadkit.contracts.exceptions import (
    DomainError,
    EventError,
    InfrastructureError,
)
from quadkit.contracts.exceptions import (
    DuplicateHandlerError as DuplicateHandlerError,
)
from quadkit.contracts.exceptions import (
    HandlerNotFoundError as HandlerNotFoundError,
)
from quadkit.contracts.exceptions import (
    NotFoundError as _BaseNotFoundError,
)
from quadkit.contracts.exceptions import (
    ValidationError as ValidationError,
)

# expose a simple alias for convenience (unchanged from contracts)
NotFoundError = _BaseNotFoundError


# ============================================================================
# CQRS-Level Exceptions
# ============================================================================


class ConcurrencyError(EventError):
    """Concurrency/optimistic locking error.

    Raised when event version conflicts indicate concurrent modifications.
    """

    _code = "QK_ERR_EVT_004"

    def __init__(
        self,
        message: str = "Concurrency error",
        expected_version: int | None = None,
        actual_version: int | None = None,
        **kwargs: Any,
    ) -> None:
        details = kwargs.get("details", {})
        if expected_version is not None:
            details["expected_version"] = expected_version
        if actual_version is not None:
            details["actual_version"] = actual_version
        kwargs["details"] = details
        super().__init__(message, **kwargs)


class CommandExecutionError(EventError):
    """Command execution error."""

    _code = "QK_ERR_EVT_005"

    def __init__(
        self,
        message: str = "Command execution failed",
        command_type: str | None = None,
        error: str | None = None,
        **kwargs: Any,
    ) -> None:
        details = kwargs.get("details", {})
        if command_type:
            details["command_type"] = command_type
        kwargs["details"] = details
        super().__init__(message, **kwargs)
        # Store as attributes for direct access (needed by tests/consumers)
        self.command_type = command_type
        self.error = error


class QueryExecutionError(EventError):
    """Query execution error."""

    _code = "QK_ERR_EVT_006"

    def __init__(
        self,
        message: str = "Query execution failed",
        query_type: str | None = None,
        error: str | None = None,
        **kwargs: Any,
    ) -> None:
        details = kwargs.get("details", {})
        if query_type:
            details["query_type"] = query_type
        kwargs["details"] = details
        super().__init__(message, **kwargs)
        # Store as attributes for direct access (needed by tests/consumers)
        self.query_type = query_type
        self.error = error


# ============================================================================
# Domain-Level Exceptions
# ============================================================================


class StreamNotFoundError(DomainError):
    """Raised when stream is not found.

    Parameters mirror the helper used in tests: (stream_type, stream_id).
    """

    _code = "QK_ERR_EVT_007"

    def __init__(
        self,
        stream_type: str,
        stream_id: str,
        message: str | None = None,
        **kwargs: Any,
    ) -> None:
        if message is None:
            message = f"{stream_type} '{stream_id}' not found"
        details = kwargs.get("details", {})
        details["stream_type"] = stream_type
        details["stream_id"] = stream_id
        kwargs["details"] = details
        super().__init__(message, **kwargs)
        self.stream_type = stream_type
        self.stream_id = stream_id


class EventHandlerError(EventError):
    """Raised when event handling fails."""

    _code: str = "QK_ERR_EVT_008"

    def __init__(
        self,
        event_type: str,
        handler: str,
        error: str,
        cause: Exception | None = None,
        **kwargs: Any,
    ):
        super().__init__(
            f"Handler {handler} for {event_type} failed: {error}",
            details={"event_type": event_type, "handler": handler, "error": error},
            cause=cause,
            **kwargs,
        )
        self.event_type = event_type
        self.handler = handler
        self.error = error


class AggregateNotFoundError(NotFoundError):
    """Raised when aggregate is not found."""

    _code: str = "QK_ERR_EVT_009"


# ============================================================================
# Infrastructure-Level Exceptions
# ============================================================================


class AdapterConnectionError(InfrastructureError):
    """Raised when adapter connection fails."""

    _code: str = "QK_ERR_EVT_010"


class EventLoadError(EventError):
    """Raised when event loading fails."""

    _code = "QK_ERR_EVT_011"

    def __init__(self, message: str = "Event load error", **kwargs: Any) -> None:
        super().__init__(message, **kwargs)


class EventPersistenceError(InfrastructureError, EventError):
    """Raised when event persistence fails."""

    _code: str = "QK_ERR_EVT_012"


class EventStoreError(EventError):
    """Raised for event store errors."""

    _code = "QK_ERR_EVT_013"

    def __init__(self, message: str = "Event store error", **kwargs: Any) -> None:
        super().__init__(message, **kwargs)


class EventStoreConnectionError(EventStoreError, AdapterConnectionError):
    """Raised when event store connection fails."""

    _code = "QK_ERR_EVT_014"

    def __init__(
        self, message: str = "Event store connection error", **kwargs: Any
    ) -> None:
        super().__init__(message, **kwargs)


# ============================================================================
# Feature-Specific Exceptions
# ============================================================================


class ProjectionBuildError(EventError):
    """Raised when projection building fails."""

    _code: str = "QK_ERR_EVT_015"


class ProjectionRebuildError(ProjectionBuildError):
    """Raised when projection rebuilding fails (alias for collection stability)."""

    _code: str = "QK_ERR_EVT_016"


class ProjectionNotFoundError(NotFoundError):
    """Raised when a projection is not found."""

    _code: str = "QK_ERR_EVT_017"


class WebhookDeliveryError(EventError):
    """Raised when an outbound webhook delivery fails after all retry attempts.

    Carries the target *url* and the HTTP *status* code returned by the
    remote endpoint so callers can log structured failure context.
    """

    _code: str = "QK_ERR_EVT_018"

    def __init__(
        self,
        url: str,
        status: int,
        message: str = "Webhook delivery failed",
        **kwargs: Any,
    ) -> None:
        super().__init__(message, details={"url": url, "status": status}, **kwargs)
        self.url = url
        self.status = status


class SchemaError(EventError):
    """Raised for schema-related errors."""

    _code: str = "QK_ERR_EVT_019"


class SecurityError(EventError):
    """Raised for security-related errors."""

    _code: str = "QK_ERR_EVT_020"


class StreamingError(EventError):
    """Raised for streaming-related errors."""

    _code: str = "QK_ERR_EVT_021"


__all__ = [
    "AdapterConnectionError",
    "AggregateNotFoundError",
    "CommandExecutionError",
    "ConcurrencyError",
    "DuplicateHandlerError",
    "EventError",
    "EventHandlerError",
    "EventLoadError",
    "EventPersistenceError",
    "EventStoreConnectionError",
    "EventStoreError",
    "HandlerNotFoundError",
    "NotFoundError",
    "ProjectionBuildError",
    "ProjectionNotFoundError",
    "ProjectionRebuildError",
    "QueryExecutionError",
    "SchemaError",
    "SecurityError",
    "StreamNotFoundError",
    "StreamingError",
    "ValidationError",
    "WebhookDeliveryError",
]
