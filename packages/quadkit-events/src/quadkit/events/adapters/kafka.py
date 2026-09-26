"""Kafka adapter for event streaming.

This module provides integration with Apache Kafka for high-throughput
event streaming across services.

Example:
    ```python
    from quadkit.events.adapters import KafkaAdapter, KafkaAdapterConfig

    config = KafkaAdapterConfig(
        bootstrap_servers=["localhost:9092"],
        topic_prefix="domain.events.",
        group_id="order-service"
    )

    adapter = KafkaAdapter(config)
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
    pip install aiokafka
"""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass
from typing import (
    TYPE_CHECKING,
    Any,
)
from uuid import uuid4

from quadkit.events.adapters.base import (
    AdapterConfig,
    MessageAdapter,
    MessageSerializer,
)
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable

    from quadkit.contracts.core import TaskManagerProtocol
    from quadkit.events.messages.event import Event

logger = get_logger(__name__)


@dataclass
class KafkaAdapterConfig(AdapterConfig):
    """Configuration for Kafka adapter.

    Attributes:
        bootstrap_servers: List of Kafka broker addresses.
        topic_prefix: Prefix for topic names.
        group_id: Consumer group ID.
        auto_offset_reset: Where to start consuming (earliest, latest).
        enable_auto_commit: Whether to auto-commit offsets.
        acks: Acknowledgment mode (all, 1, 0).
        enable_idempotence: Enable idempotent producer.
        transactional_id: Transaction ID for exactly-once semantics.
        compression_type: Compression (none, gzip, snappy, lz4, zstd).
        batch_size: Batch size for producer.
        linger_ms: Linger time for batching.
    """

    topic_prefix: str = "events."

    @property
    def bootstrap_servers(self) -> list[str]:
        """Bootstrap servers as a list of strings."""
        if isinstance(self.connection_string, list):
            return self.connection_string
        return (
            [self.connection_string] if self.connection_string else ["localhost:9092"]
        )

    group_id: str = "default-consumer-group"
    auto_offset_reset: str = "earliest"
    enable_auto_commit: bool = False
    acks: str = "all"
    enable_idempotence: bool = True
    transactional_id: str | None = None
    compression_type: str = "gzip"
    batch_size: int = 16384
    linger_ms: int = 5


class KafkaAdapter(MessageAdapter["Event"]):
    """Kafka adapter for high-throughput event streaming.

    This adapter uses aiokafka to publish events to Kafka
    and subscribe to event topics.

    Example:
        ```python
        adapter = KafkaAdapter(KafkaAdapterConfig(
            bootstrap_servers=["localhost:9092"],
            topic_prefix="events."
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
        config: KafkaAdapterConfig,
        serializer: MessageSerializer | None = None,
        task_manager: TaskManagerProtocol | None = None,
    ) -> None:
        """Initialize Kafka adapter.

        Args:
            config: Kafka configuration.
            serializer: Message serializer.
            task_manager: Task manager for background tasks.
        """
        super().__init__(config, serializer)
        self.config: KafkaAdapterConfig = config
        self._task_manager = task_manager
        self._producer: Any = None
        self._consumers: dict[str, Any] = {}
        self._consumer_tasks: dict[str, asyncio.Task] = {}

    async def connect(self) -> None:
        """Connect to Kafka.

        Raises:
            ConnectionError: If connection fails.
        """
        try:
            from aiokafka import AIOKafkaProducer
        except ImportError as e:
            raise ImportError(
                "aiokafka is required for Kafka adapter. "
                "Install with: pip install aiokafka",
            ) from e

        try:
            self._producer = AIOKafkaProducer(
                bootstrap_servers=self.config.bootstrap_servers,
                acks=self.config.acks,
                enable_idempotence=self.config.enable_idempotence,
                compression_type=self.config.compression_type,
                linger_ms=self.config.linger_ms,
                transactional_id=self.config.transactional_id,
            )

            await self._producer.start()

            if self.config.transactional_id:
                await self._producer.begin_transaction()

            self._connected = True
            logger.info("Connected to Kafka: %s", self.config.bootstrap_servers)

        except Exception as e:  # noqa: BLE001 — wraps unknown aiokafka connection failure as AdapterConnectionError
            logger.exception("Failed to connect to Kafka")
            from quadkit.events.exceptions import AdapterConnectionError

            raise AdapterConnectionError(f"Kafka: {e}", cause=e) from e

    async def disconnect(self) -> None:
        """Disconnect from Kafka."""
        # Stop consumers
        for sub_id in list(self._consumer_tasks.keys()):
            await self.unsubscribe(sub_id)

        # Stop producer
        if self._producer:
            if self.config.transactional_id:
                try:
                    await self._producer.commit_transaction()
                except (ConnectionError, RuntimeError, ValueError, TypeError):
                    with contextlib.suppress(OSError, ValueError, TypeError):
                        logger.exception("Failed to commit Kafka transaction, aborting")
                    try:
                        await self._producer.abort_transaction()
                    except (
                        ConnectionError,
                        RuntimeError,
                        ValueError,
                        TypeError,
                    ):
                        with contextlib.suppress(OSError, ValueError, TypeError):
                            logger.exception(
                                "Failed to abort Kafka transaction",
                            )
            await self._producer.stop()
        self._connected = False
        logger.info("Disconnected from Kafka")

    async def publish(self, event: Event) -> None:
        """Publish an event to Kafka.

        Args:
            event: The event to publish.

        Raises:
            RuntimeError: If not connected.
        """
        if not self._connected or not self._producer:
            raise RuntimeError("Not connected to Kafka")

        try:
            topic = f"{self.config.topic_prefix}{type(event).__name__}"
            headers = self._create_headers(event)

            key = str(getattr(event, "aggregate_id", "")).encode()
            value = self.serializer.serialize(event)

            # Convert headers to Kafka format
            kafka_headers = [
                (
                    key,
                    value.encode() if isinstance(value, str) else str(value).encode(),
                )
                for key, value in headers.to_dict().items()
            ]

            await self._with_retry(
                self._producer.send_and_wait,
                topic=topic,
                key=key,
                value=value,
                headers=kafka_headers,
            )

            logger.debug("Published event to %s: %s", topic, type(event).__name__)

        except (ConnectionError, RuntimeError, ValueError, TypeError) as e:
            logger.exception("Failed to publish event")
            raise RuntimeError(f"Failed to publish event: {e}") from e

    async def subscribe(
        self,
        event_types: list[str],
        handler: Callable[[Event], Any],
    ) -> str:
        """Subscribe to events from Kafka.

        Args:
            event_types: List of event type names to subscribe to.
            handler: Handler function for received events.

        Returns:
            Subscription ID.

        Raises:
            RuntimeError: If not connected.
        """
        if not self._connected:
            raise RuntimeError("Not connected to Kafka")

        try:
            from aiokafka import AIOKafkaConsumer
        except ImportError as e:
            raise ImportError(
                "aiokafka is required for Kafka adapter. "
                "Install with: pip install aiokafka",
            ) from e

        try:
            subscription_id = str(uuid4())
            topics = [f"{self.config.topic_prefix}{et}" for et in event_types]

            consumer = AIOKafkaConsumer(
                *topics,
                bootstrap_servers=self.config.bootstrap_servers,
                group_id=self.config.group_id,
                auto_offset_reset=self.config.auto_offset_reset,
                enable_auto_commit=self.config.enable_auto_commit,
            )

            await consumer.start()
            self._consumers[subscription_id] = consumer

            # Start consumer task
            async def consume_loop() -> None:
                try:
                    with contextlib.suppress(asyncio.CancelledError):
                        async for message in consumer:
                            try:
                                # Extract event type from headers
                                headers_dict = {
                                    k: v.decode() if v else ""
                                    for k, v in (message.headers or [])
                                }
                                event_type = headers_dict.get("event_type", "Unknown")

                                event = self.serializer.deserialize(
                                    message.value,
                                    event_type,
                                )

                                result = handler(event)
                                if asyncio.iscoroutine(result):
                                    await result

                                # Commit offset
                                if not self.config.enable_auto_commit:
                                    await consumer.commit()

                            except Exception:  # noqa: BLE001 — per-message isolation: one bad message must not kill the consumer
                                logger.exception("Error processing message")

                except Exception:  # noqa: BLE001 — the consumer loop must log and survive any failure
                    logger.exception("Consumer loop error")

            from quadkit.concurrency.executors.task_manager import TaskManager

            task_manager = self._task_manager or TaskManager()
            task = task_manager.create_critical_task(
                consume_loop(),
                name=f"kafka_consumer_{subscription_id}",
            )

            def _log_task_result(t: asyncio.Task) -> None:
                try:
                    # Avoid calling t.exception() directly. Mocks can trigger
                    # coroutine side-effects when t.exception() is accessed.
                    if t.cancelled():
                        return
                    if t.done():
                        logger.error(
                            "Consumer task completed with an exception",
                        )
                except (AttributeError, RuntimeError, ValueError):
                    with contextlib.suppress(OSError, ValueError, TypeError):
                        logger.exception("Error in consumer done-callback")

            try:
                # add_done_callback does not return a value per stdlib.
                # Some test doubles may return a coroutine; be defensive.
                res = task.add_done_callback(_log_task_result)

                result: Any = res
                # Some test doubles (e.g. AsyncMock) may return coroutine objects
                # when invoked; schedule them to avoid un-awaited coroutine warnings.
                if asyncio.iscoroutine(result):
                    task_manager.create_background_task(
                        result,
                        name=f"kafka_callback_{subscription_id}",
                    )
            except (AttributeError, TypeError, ValueError):
                with contextlib.suppress(OSError, ValueError, TypeError):
                    logger.exception("Failed to register consumer callback")
            self._consumer_tasks[subscription_id] = task

            logger.info(
                "Subscribed to Kafka topics: %s (ID: %s)",
                topics,
                subscription_id,
            )
            return subscription_id

        except (ConnectionError, RuntimeError, ValueError, TypeError, ImportError) as e:
            logger.exception("Failed to subscribe")
            raise RuntimeError(f"Failed to subscribe: {e}") from e

    async def unsubscribe(self, subscription_id: str) -> None:
        """Unsubscribe from events.

        Args:
            subscription_id: ID of the subscription to cancel.
        """
        # Cancel task
        if subscription_id in self._consumer_tasks:
            task = self._consumer_tasks.pop(subscription_id)
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

        # Stop consumer
        if subscription_id in self._consumers:
            consumer = self._consumers.pop(subscription_id)
            await consumer.stop()
            logger.info("Unsubscribed from Kafka: %s", subscription_id)

    async def publish_batch(self, events: list[Event]) -> None:
        """Publish multiple events as a batch.

        Args:
            events: List of events to publish.
        """
        if not self._connected or not self._producer:
            raise RuntimeError("Not connected to Kafka")

        # Simplified implementation - publish each event individually
        for event in events:
            await self.publish(event)

    async def begin_transaction(self) -> None:
        """Begin a Kafka transaction.

        Requires transactional_id to be set in config.
        """
        if not self._producer or not self.config.transactional_id:
            raise RuntimeError("Transactions require producer and transactional_id")
        await self._producer.begin_transaction()

    async def commit_transaction(self) -> None:
        """Commit the current Kafka transaction."""
        if self._producer and self.config.transactional_id:
            await self._producer.commit_transaction()

    async def abort_transaction(self) -> None:
        """Abort the current Kafka transaction."""
        if self._producer and self.config.transactional_id:
            await self._producer.abort_transaction()

    async def get_topic_partitions(self, topic: str) -> list[int]:
        """Get partition IDs for a topic.

        Args:
            topic: Topic name.

        Returns:
            List of partition IDs.
        """
        if not self._producer:
            raise RuntimeError("Not connected to Kafka")

        partitions = await self._producer.partitions_for(topic)
        return list(partitions) if partitions else []
