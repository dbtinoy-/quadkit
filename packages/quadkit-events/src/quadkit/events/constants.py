"""Package-level constants for quadkit-events.

This module centralises magic strings used throughout the events package.
Constants are grouped into :class:`~enum.StrEnum` namespaces for IDE
discoverability and type safety.
"""

from __future__ import annotations

from enum import StrEnum
import importlib.metadata

# -- Version -------------------------------------------------------------------

try:
    __version__: str = importlib.metadata.version("quadkit-events")
except ImportError:
    __version__ = "0.0.0"


# ---------------------------------------------------------------------------
# Configuration environment variable constants
# ---------------------------------------------------------------------------

ENV_PREFIX: str = "QK_EVENTS__"
ENV_NESTED_DELIMITER: str = "__"


# ---------------------------------------------------------------------------
# Enum namespaces
# ---------------------------------------------------------------------------


class HandlerType(StrEnum):
    """Discriminator values for the CQRS handler-type registry."""

    COMMAND = "command"
    QUERY = "query"
    EVENT = "event"
    SAGA = "saga"
    PROJECTION = "projection"


class StoreType(StrEnum):
    """Supported event-store backend identifiers."""

    MEMORY = "memory"
    POSTGRES = "postgres"
    MONGODB = "mongodb"
    SQLITE = "sqlite"


class HealthStatus(StrEnum):
    """Health-check outcome labels."""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


class OperationStatus(StrEnum):
    """Generic operation lifecycle statuses."""

    SUCCESS = "success"
    ERROR = "error"
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class MessageMetaKey(StrEnum):
    """Metadata keys present in every domain-event envelope."""

    MESSAGE_TYPE = "message_type"
    MESSAGE_ID = "message_id"
    TIMESTAMP = "timestamp"
    CORRELATION_ID = "correlation_id"
    CAUSATION_ID = "causation_id"


class TransactionPropagation(StrEnum):
    """Transactional propagation behaviour."""

    REQUIRED = "required"
    REQUIRES_NEW = "requires_new"
    SUPPORTS = "supports"


class WebSocketMessageType(StrEnum):
    """WebSocket control-message type discriminators."""

    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    PING = "ping"
    PONG = "pong"


class FilterOperator(StrEnum):
    """Boolean operators for composite event-store filters."""

    AND = "and"
    OR = "or"


class SchemaType(StrEnum):
    """JSON-Schema primitive type names."""

    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"
    NULL = "null"


class EnvelopeField(StrEnum):
    """Canonical field names used in domain-event envelopes."""

    EVENT_TYPE = "event_type"
    TIMESTAMP = "timestamp"
    AGGREGATE_ID = "aggregate_id"
    AGGREGATE_TYPE = "aggregate_type"
    VERSION = "version"
    CORRELATION_ID = "correlation_id"
    CAUSATION_ID = "causation_id"
    METADATA = "metadata"
    EVENT_DATA = "event_data"


# ---------------------------------------------------------------------------
# __all__
# ---------------------------------------------------------------------------

__all__ = [
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
