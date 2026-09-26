"""Base adapter interfaces and utilities.

This module provides base classes and utilities for message queue adapters.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import (
    TYPE_CHECKING,
    Any,
    Generic,
    Protocol,
    TypeVar,
)

from quadkit.serialization import dumps, loads

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from quadkit.events.messages.event import Event


EventT = TypeVar("EventT", bound="Event")


class MessageSerializer(Protocol):
    """Protocol for message serialization."""

    def serialize(self, event: Event) -> bytes:
        """Serialize an event to bytes."""
        ...

    def deserialize(self, data: bytes, event_type: str) -> Event:
        """Deserialize bytes to an event."""
        ...


class DefaultMessageSerializer:
    """Default JSON-based message serializer.

    This serializer uses Pydantic's model_dump_json for serialization
    and reconstructs events based on event type registration.

    Example:
        ```python
        serializer = DefaultMessageSerializer()
        serializer.register_event_type(UserCreatedEvent)

        # Serialize
        data = serializer.serialize(event)

        # Deserialize
        event = serializer.deserialize(data, "UserCreatedEvent")
        ```
    """

    def __init__(self) -> None:
        """Initialize the serializer."""
        self._event_types: dict[str, type[Event]] = {}

    def register_event_type(self, event_class: type[Event]) -> None:
        """Register an event type for deserialization.

        Args:
            event_class: The event class to register.
        """
        self._event_types[event_class.__name__] = event_class

    def register_event_types(self, *event_classes: type[Event]) -> None:
        """Register multiple event types.

        Args:
            *event_classes: Event classes to register.
        """
        for event_class in event_classes:
            self.register_event_type(event_class)

    def serialize(self, event: Event) -> bytes:
        """Serialize an event to JSON bytes.

        Args:
            event: The event to serialize.

        Returns:
            JSON-encoded bytes.
        """
        if hasattr(event, "model_dump_json"):
            payload: bytes = event.model_dump_json().encode()
            return payload

        # dataclass-backed events don't expose ``model_dump_json``; we
        # simply serialize their instance dictionary directly.  This keeps
        # all attributes (including user-provided payload fields) at the
        # top level rather than wrapped inside a ``data`` key.  The
        # caller still provides ``event_type`` separately during
        # deserialization.
        event_dict = getattr(event, "__dict__", {}).copy()
        # ensure the event type appears in the payload too for legacy
        # consumers that might inspect it
        event_dict.setdefault("event_type", type(event).__name__)
        return dumps(event_dict, default=str)

    def deserialize(self, data: bytes, event_type: str) -> Event:
        """Deserialize bytes to an event.

        Args:
            data: JSON-encoded bytes.
            event_type: The event type name.

        Returns:
            Deserialized event.

        Raises:
            ValueError: If event type is not registered.
        """
        if event_type not in self._event_types:
            raise ValueError(f"Unknown event type: {event_type}")

        event_class = self._event_types[event_type]
        json_data = loads(data)

        if hasattr(event_class, "model_validate"):
            parsed: Event = event_class.model_validate(json_data)
            return parsed
        return event_class(**json_data)


@dataclass
class AdapterConfig:
    """Base configuration for message adapters.

    Attributes:
        connection_string: Connection string or list of server addresses.
        timeout: Connection timeout in seconds.
        reconnect_attempts: Number of reconnection attempts.
        reconnect_delay: Delay between reconnection attempts.
        enable_logging: Whether to log adapter activity.
    """

    connection_string: str | list[str] = ""
    timeout: float = 30.0
    reconnect_attempts: int = 3
    reconnect_delay: float = 1.0
    enable_logging: bool = True


@dataclass
class MessageHeaders:
    """Standard message headers.

    Attributes:
        event_type: Type name of the event.
        aggregate_id: ID of the aggregate.
        aggregate_type: Type of the aggregate.
        timestamp: Event timestamp.
        correlation_id: Correlation ID for tracing.
        causation_id: ID of the causing event.
        metadata: Additional metadata.
    """

    event_type: str
    aggregate_id: str | None = None
    aggregate_type: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    causation_id: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, str]:
        """Convert headers to a string dictionary."""
        result = {
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat(),
        }
        if self.aggregate_id:
            result["aggregate_id"] = self.aggregate_id
        if self.aggregate_type:
            result["aggregate_type"] = self.aggregate_type
        if self.correlation_id:
            result["correlation_id"] = self.correlation_id
        if self.causation_id:
            result["causation_id"] = self.causation_id
        result.update(self.metadata)
        return result

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> MessageHeaders:
        """Create headers from a mapping and coerce values to strings."""
        return cls(
            event_type=str(data.get("event_type", "Unknown")),
            aggregate_id=data.get("aggregate_id") and str(data.get("aggregate_id")),
            aggregate_type=data.get("aggregate_type")
            and str(data.get("aggregate_type")),
            timestamp=datetime.fromisoformat(
                str(data.get("timestamp", datetime.now(UTC).isoformat())),
            ),
            correlation_id=data.get("correlation_id")
            and str(data.get("correlation_id")),
            causation_id=data.get("causation_id") and str(data.get("causation_id")),
            metadata={
                k: str(v)
                for k, v in dict(data).items()
                if k
                not in {
                    "event_type",
                    "aggregate_id",
                    "aggregate_type",
                    "timestamp",
                    "correlation_id",
                    "causation_id",
                }
            },
        )


class MessageAdapter(ABC, Generic[EventT]):
    """Abstract base class for message queue adapters.

    Message adapters provide integration with external message queues
    for publishing and subscribing to events across services.

    Example:
        ```python
        class MyAdapter(MessageAdapter[Event]):
            async def connect(self) -> None:
                # Connect to message queue
                pass

            async def publish(self, event: Event) -> None:
                # Publish event
                pass

            async def subscribe(
                self,
                event_types: list[str],
                handler: Callable[[Event], Awaitable[None]]
            ) -> None:
                # Subscribe to events
                pass
        ```
    """

    def __init__(
        self,
        config: AdapterConfig,
        serializer: MessageSerializer | None = None,
    ) -> None:
        """Initialize the adapter.

        Args:
            config: Adapter configuration.
            serializer: Message serializer (defaults to JSON).
        """
        self.config = config
        self.serializer = serializer or DefaultMessageSerializer()
        self._connected = False

    @property
    def is_connected(self) -> bool:
        """Check if the adapter is connected."""
        return self._connected

    @abstractmethod
    async def connect(self) -> None:
        """Connect to the message queue.

        Raises:
            ConnectionError: If connection fails.
        """
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the message queue."""
        ...

    @abstractmethod
    async def publish(self, event: EventT) -> None:
        """Publish an event to the message queue.

        Args:
            event: The event to publish.

        Raises:
            PublishError: If publishing fails.
        """
        ...

    @abstractmethod
    async def subscribe(
        self,
        event_types: list[str],
        handler: Callable[[EventT], Any],
    ) -> str:
        """Subscribe to events from the message queue.

        Args:
            event_types: List of event type names to subscribe to.
            handler: Handler function for received events.

        Returns:
            Subscription ID.

        Raises:
            SubscriptionError: If subscription fails.
        """
        ...

    @abstractmethod
    async def unsubscribe(self, subscription_id: str) -> None:
        """Unsubscribe from events.

        Args:
            subscription_id: ID of the subscription to cancel.
        """
        ...

    def _create_headers(self, event: EventT) -> MessageHeaders:
        """Create message headers from an event."""
        return MessageHeaders(
            event_type=type(event).__name__,
            aggregate_id=str(getattr(event, "aggregate_id", "")),
            aggregate_type=getattr(event, "aggregate_type", None),
            timestamp=getattr(event, "timestamp", datetime.now(UTC)),
            correlation_id=getattr(event, "correlation_id", None),
            causation_id=getattr(event, "causation_id", None),
        )

    async def _with_retry(
        self,
        operation: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Execute an operation with retry logic (M-25)."""
        import asyncio
        import contextlib

        from quadkit.contracts.infra.resilience.models import RetryConfig
        from quadkit.events.adapters.retry import retry

        config = RetryConfig(
            max_attempts=self.config.reconnect_attempts + 1,
            base_delay=self.config.reconnect_delay,
            backoff_factor=2.0,
            retry_on=(ConnectionError, RuntimeError, TimeoutError, OSError),
        )

        async def _wrapper() -> Any:
            # Try to reconnect if not connected (unless the operation IS connect)
            if not self._connected and getattr(operation, "__name__", "") != "connect":
                with contextlib.suppress(Exception):
                    await self.connect()

            result = operation(*args, **kwargs)
            if asyncio.iscoroutine(result):
                return await result
            return result

        try:
            return await retry(_wrapper, config=config)
        except Exception as e:  # noqa: BLE001 — unwraps RetryError to surface last_error; re-raises all others
            from quadkit.contracts.exceptions.resilience import RetryError

            if isinstance(e, RetryError) and hasattr(e, "last_error") and e.last_error:
                raise e.last_error from e
            raise

    async def __aenter__(self) -> MessageAdapter[EventT]:
        """Async context manager entry."""
        await self._with_retry(self.connect)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Async context manager exit."""
        await self.disconnect()
