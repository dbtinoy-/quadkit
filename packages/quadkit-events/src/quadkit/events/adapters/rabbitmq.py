"""RabbitMQ adapter for event distribution.

This module provides integration with RabbitMQ for publishing and
subscribing to events across services.

Example:
    ```python
    from quadkit.events.adapters import RabbitMQAdapter, RabbitMQAdapterConfig

    config = RabbitMQAdapterConfig(
        connection_string=SecretStr("amqp://localhost/"),
        exchange_name="domain_events",
        queue_name="order_service"
    )

    adapter = RabbitMQAdapter(config)
    await adapter.connect()

    # Publish events
    await adapter.publish(OrderCreatedEvent(...))

    # Subscribe to events
    await adapter.subscribe(
        ["OrderCreated", "OrderShipped"],
        handler=handle_order_event
    )
    ```

Requirements:
    pip install aio-pika
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import (
    TYPE_CHECKING,
    Any,
    cast,
)
from uuid import uuid4

from quadkit.events.adapters.base import (
    AdapterConfig,
    MessageAdapter,
    MessageSerializer,
)
from quadkit.logging import get_logger
from quadkit.validation import SecretStr

if TYPE_CHECKING:
    from collections.abc import Callable

    from quadkit.events.messages.event import Event

logger = get_logger(__name__)


@dataclass
class RabbitMQAdapterConfig(AdapterConfig):
    """Configuration for RabbitMQ adapter.

    Attributes:
        connection_string: AMQP connection string.
        exchange_name: Name of the exchange for events.
        exchange_type: Type of exchange (topic, direct, fanout).
        queue_name: Name of the queue for receiving events.
        queue_durable: Whether the queue is durable.
        prefetch_count: Number of messages to prefetch.
        heartbeat: Heartbeat interval in seconds.
        routing_key_prefix: Prefix for routing keys.
    """

    connection_string: SecretStr  # type: ignore[assignment]
    exchange_name: str = "domain_events"
    exchange_type: str = "topic"
    queue_name: str = ""
    queue_durable: bool = True
    prefetch_count: int = 10
    heartbeat: int = 60
    routing_key_prefix: str = "events."

    def __post_init__(self) -> None:
        """Coerce connection_string to SecretStr at construction time."""
        if isinstance(self.connection_string, str):
            self.connection_string = SecretStr(self.connection_string)


class RabbitMQAdapter(MessageAdapter["Event"]):
    """RabbitMQ adapter for event distribution.

    This adapter uses aio-pika to publish events to RabbitMQ
    and subscribe to event topics.

    Example:
        ```python
        adapter = RabbitMQAdapter(RabbitMQAdapterConfig(
            connection_string="amqp://localhost/",
            exchange_name="events"
        ))

        async with adapter:
            # Publish
            await adapter.publish(MyEvent(...))

            # Subscribe
            sub_id = await adapter.subscribe(
                ["MyEvent"],
                handler=process_event
            )
        ```
    """

    def __init__(
        self,
        config: RabbitMQAdapterConfig,
        serializer: MessageSerializer | None = None,
    ) -> None:
        """Initialize RabbitMQ adapter.

        Args:
            config: RabbitMQ configuration.
            serializer: Message serializer.
        """
        super().__init__(config, serializer)
        self.config: RabbitMQAdapterConfig = config
        self._connection: Any = None
        self._channel: Any = None
        self._exchange: Any = None
        self._subscriptions: dict[str, Any] = {}

    async def connect(self) -> None:
        """Connect to RabbitMQ.

        Raises:
            ConnectionError: If connection fails.
        """
        try:
            import aio_pika
        except ImportError as e:
            raise ImportError(
                "aio-pika is required for RabbitMQ adapter. "
                "Install with: pip install aio-pika",
            ) from e

        try:
            self._connection = await aio_pika.connect_robust(
                self.config.connection_string.get_secret_value(),
                heartbeat=self.config.heartbeat,
                timeout=self.config.timeout,
            )

            self._channel = await self._connection.channel()
            await self._channel.set_qos(prefetch_count=self.config.prefetch_count)

            # Declare exchange
            exchange_type = getattr(
                aio_pika.ExchangeType,
                self.config.exchange_type.upper(),
            )
            self._exchange = await self._channel.declare_exchange(
                self.config.exchange_name,
                exchange_type,
                durable=True,
            )

            self._connected = True
            logger.info("Connected to RabbitMQ")

        except Exception as e:  # noqa: BLE001 — wraps unknown aio-pika connection failure as AdapterConnectionError
            logger.error("Failed to connect to RabbitMQ: %s", e)
            from quadkit.events.exceptions import AdapterConnectionError

            raise AdapterConnectionError(f"RabbitMQ: {e}", cause=e) from e

    async def disconnect(self) -> None:
        """Disconnect from RabbitMQ."""
        # Cancel subscriptions
        for sub_id in list(self._subscriptions.keys()):
            await self.unsubscribe(sub_id)

        if self._connection:
            await self._connection.close()
            self._connection = None
            self._channel = None
            self._exchange = None

        self._connected = False
        logger.info("Disconnected from RabbitMQ")

    async def cancel_scheduled_message(self, sequence_number: int) -> None:
        """Cancel a scheduled message.

        Args:
            sequence_number: Sequence number to cancel.
        """
        # Implementation for canceling a scheduled message would go here.
        # This method is a placeholder as RabbitMQ does not natively support
        # canceling individual scheduled messages without external tracking.
        logger.warning(
            "Canceling scheduled messages is not directly supported by RabbitMQ "
            "without external tracking. This method is a placeholder.",
        )

    async def publish(self, event: Event) -> None:
        """Publish an event to RabbitMQ.

        Args:
            event: The event to publish.

        Raises:
            RuntimeError: If not connected.
            PublishError: If publishing fails.
        """
        if not self._connected or not self._exchange:
            raise RuntimeError("Not connected to RabbitMQ")

        try:
            import aio_pika

            routing_key = f"{self.config.routing_key_prefix}{type(event).__name__}"
            headers = self._create_headers(event)

            message = aio_pika.Message(
                body=self.serializer.serialize(event),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                content_type="application/json",
                headers=cast("dict[str, Any]", headers.to_dict()),
            )

            await self._with_retry(
                self._exchange.publish,
                message,
                routing_key=routing_key,
            )
            logger.debug("Published event: %s", type(event).__name__)

        except Exception as e:  # noqa: BLE001 — wraps unknown aio-pika publish failure as RuntimeError
            logger.error("Failed to publish event: %s", e)
            raise RuntimeError(f"Failed to publish event: {e}") from e

    async def subscribe(
        self,
        event_types: list[str],
        handler: Callable[[Event], Any],
    ) -> str:
        """Subscribe to events from RabbitMQ.

        Args:
            event_types: List of event type names to subscribe to.
            handler: Handler function for received events.

        Returns:
            Subscription ID.

        Raises:
            RuntimeError: If not connected.
        """
        if not self._connected or not self._channel:
            raise RuntimeError("Not connected to RabbitMQ")

        try:
            subscription_id = str(uuid4())

            # Create queue
            queue_name = self.config.queue_name or f"sub-{subscription_id}"
            queue = await self._channel.declare_queue(
                queue_name,
                durable=self.config.queue_durable,
            )

            # Bind to event types
            for event_type in event_types:
                routing_key = f"{self.config.routing_key_prefix}{event_type}"
                await queue.bind(self._exchange, routing_key=routing_key)

            # Start consuming
            async def process_message(message: Any) -> None:
                async with message.process():
                    try:
                        event_type = message.headers.get("event_type", "Unknown")
                        event = self.serializer.deserialize(message.body, event_type)

                        result = handler(event)
                        if asyncio.iscoroutine(result):
                            await result

                    except Exception as e:  # noqa: BLE001 — logs per-message error and re-raises for aio-pika to nack
                        logger.exception("Error processing message", error=str(e))
                        raise

            consumer_tag = await queue.consume(process_message)

            self._subscriptions[subscription_id] = {
                "queue": queue,
                "consumer_tag": consumer_tag,
                "event_types": event_types,
            }

            logger.info(
                "Subscribed to events: %s (ID: %s)",
                event_types,
                subscription_id,
            )
            return subscription_id

        except Exception as e:  # noqa: BLE001 — wraps subscribe setup failure as RuntimeError
            logger.exception("Failed to subscribe")
            raise RuntimeError(f"Failed to subscribe: {e}") from e

    async def unsubscribe(self, subscription_id: str) -> None:
        """Unsubscribe from events.

        Args:
            subscription_id: ID of the subscription to cancel.
        """
        if subscription_id not in self._subscriptions:
            return

        sub = self._subscriptions.pop(subscription_id)
        try:
            await sub["queue"].cancel(sub["consumer_tag"])
            logger.info("Unsubscribed: %s", subscription_id)
        except Exception as e:  # noqa: BLE001 — best-effort unsubscribe cleanup; log and continue
            logger.exception("Error unsubscribing", error=str(e))

    async def publish_batch(self, events: list[Event]) -> None:
        """Publish multiple events in a batch.

        Args:
            events: List of events to publish.
        """
        for event in events:
            await self.publish(event)

    async def create_dead_letter_queue(
        self,
        queue_name: str,
        ttl: int = 86400,
    ) -> None:
        """Create a dead letter queue for failed messages.

        Args:
            queue_name: Name of the dead letter queue.
            ttl: Time-to-live for messages in seconds.
        """
        if not self._connected or not self._channel:
            raise RuntimeError("Not connected to RabbitMQ")

        try:
            import aio_pika

            # Create DLX exchange
            await self._channel.declare_exchange(
                f"{self.config.exchange_name}.dlx",
                aio_pika.ExchangeType.TOPIC,
                durable=True,
            )

            # Create DLQ
            await self._channel.declare_queue(
                queue_name,
                durable=True,
                arguments={
                    "x-message-ttl": ttl * 1000,
                },
            )

            logger.info("Created dead letter queue: %s", queue_name)

        except Exception as e:  # noqa: BLE001 — wraps DLQ creation failure; re-raises
            logger.exception("Failed to create DLQ", error=str(e))
            raise
