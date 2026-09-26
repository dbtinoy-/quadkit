"""Azure Service Bus adapter for event distribution.

This module provides integration with Azure Service Bus for cloud-native
event distribution across services.

Example:
    ```python
    from quadkit.events.adapters import AzureServiceBusAdapter, AzureServiceBusAdapterConfig

    config = AzureServiceBusAdapterConfig(
        connection_string="Endpoint=sb://...",
        topic_name="domain-events",
        subscription_name="order-service"
    )

    adapter = AzureServiceBusAdapter(config)
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
    pip install azure-servicebus
"""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass
from typing import (
    TYPE_CHECKING,
    Any,
    cast,
)
from uuid import UUID, uuid4

from quadkit.events.adapters.base import (
    AdapterConfig,
    MessageAdapter,
    MessageSerializer,
)
from quadkit.logging import get_logger
from quadkit.validation import SecretStr

if TYPE_CHECKING:
    from collections.abc import Callable

    from quadkit.contracts.core import TaskManagerProtocol
    from quadkit.events.messages.event import Event

logger = get_logger(__name__)


@dataclass
class AzureServiceBusAdapterConfig(AdapterConfig):
    """Configuration for Azure Service Bus adapter.

    Attributes:
        connection_string: Azure Service Bus connection string.
        topic_name: Name of the topic for events.
        subscription_name: Name of the subscription.
        max_delivery_count: Maximum delivery count.
        lock_duration: Lock duration in seconds.
        auto_complete: Whether to autocomplete messages.
        prefetch_count: Number of messages to prefetch.
        max_concurrent_calls: Maximum concurrent calls.
    """

    connection_string: SecretStr  # type: ignore[assignment]
    topic_name: str = "domain-events"

    subscription_name: str = ""
    max_delivery_count: int = 10
    lock_duration: int = 60
    auto_complete: bool = False
    prefetch_count: int = 10
    max_concurrent_calls: int = 1

    def __post_init__(self) -> None:
        """Coerce connection_string to SecretStr at construction time."""
        if isinstance(self.connection_string, str):
            self.connection_string = SecretStr(self.connection_string)


class AzureServiceBusAdapter(MessageAdapter["Event"]):
    """Azure Service Bus adapter for cloud event distribution.

    This adapter uses azure-servicebus to publish events to Azure Service Bus
    topics and subscribe via subscriptions.

    Example:
        ```python
        adapter = AzureServiceBusAdapter(AzureServiceBusAdapterConfig(
            connection_string="Endpoint=sb://...",
            topic_name="events"
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
        config: AzureServiceBusAdapterConfig,
        serializer: MessageSerializer | None = None,
        task_manager: TaskManagerProtocol | None = None,
    ) -> None:
        """Initialize Azure Service Bus adapter.

        Args:
            config: Azure Service Bus configuration.
            serializer: Message serializer.
            task_manager: Task manager for background tasks.
        """
        super().__init__(config, serializer)
        self.config: AzureServiceBusAdapterConfig = config
        self._task_manager = task_manager
        self._client: Any = None
        self._sender: Any = None
        self._receivers: dict[str, Any] = {}
        self._receiver_tasks: dict[str, asyncio.Task] = {}

    async def connect(self) -> None:
        """Connect to Azure Service Bus.

        Raises:
            ConnectionError: If connection fails.
        """
        try:
            from azure.servicebus.aio import (
                ServiceBusClient,
            )
        except ImportError as e:
            raise ImportError(
                "azure-servicebus is required for Azure Service Bus adapter. "
                "Install with: pip install azure-servicebus",
            ) from e

        try:
            # Avoid treating ServiceBusClient as a typed object; cast to Any
            # before calling the helper constructor to satisfy static analyzers.
            from typing import cast

            self._client = cast("Any", ServiceBusClient).from_connection_string(
                self.config.connection_string.get_secret_value(),
            )

            self._sender = await self._client.get_topic_sender(
                topic_name=self.config.topic_name,
            )

            self._connected = True
            logger.info(
                "Connected to Azure Service Bus topic: %s",
                self.config.topic_name,
            )

        except Exception as e:  # noqa: BLE001 — wraps unknown Azure SDK connection failure as AdapterConnectionError
            logger.exception("Failed to connect to Azure Service Bus")
            from quadkit.events.exceptions import (
                AdapterConnectionError,
            )

            raise AdapterConnectionError(
                f"Azure Service Bus: {e}",
                cause=e,
            ) from e

    async def disconnect(self) -> None:
        """Disconnect from Azure Service Bus."""
        # Stop receivers
        for sub_id in list(self._receiver_tasks.keys()):
            await self.unsubscribe(sub_id)

        # Close sender
        if self._sender:
            await self._sender.close()
            self._sender = None

        # Close client
        if self._client:
            await self._client.close()
            self._client = None

        self._connected = False
        logger.info("Disconnected from Azure Service Bus")

    async def publish(self, event: Event) -> None:
        """Publish an event to Azure Service Bus.

        Args:
            event: The event to publish.

        Raises:
            RuntimeError: If not connected.
        """
        if not self._connected or not self._sender:
            raise RuntimeError("Not connected to Azure Service Bus")

        try:
            from azure.servicebus import (
                ServiceBusMessage,
            )
        except ImportError as e:
            raise ImportError(
                "azure-servicebus is required for Azure Service Bus adapter.",
            ) from e

        try:
            headers = self._create_headers(event)
            body = self.serializer.serialize(event)

            message = ServiceBusMessage(
                body=body,
                content_type="application/json",
                subject=type(event).__name__,
                application_properties=cast(
                    "dict[str | bytes, int | float | bytes | bool | str | UUID]",
                    headers.to_dict(),
                ),
            )

            await self._sender.send_messages(message)
            logger.debug("Published event: %s", type(event).__name__)

        except Exception as e:  # noqa: BLE001 — wraps unknown Azure SDK publish failure as RuntimeError
            logger.exception("Failed to publish event")
            raise RuntimeError(f"Failed to publish event: {e}") from e

    async def subscribe(
        self,
        event_types: list[str],
        handler: Callable[[Event], Any],
    ) -> str:
        """Subscribe to events from Azure Service Bus.

        Args:
            event_types: List of event type names to subscribe to.
            handler: Handler function for received events.

        Returns:
            Subscription ID.

        Raises:
            RuntimeError: If not connected.
        """
        if not self._connected or not self._client:
            raise RuntimeError("Not connected to Azure Service Bus")

        try:
            subscription_id = str(uuid4())
            subscription_name = (
                self.config.subscription_name or f"sub-{subscription_id[:8]}"
            )

            receiver = await self._client.get_subscription_receiver(
                topic_name=self.config.topic_name,
                subscription_name=subscription_name,
                prefetch_count=self.config.prefetch_count,
            )

            self._receivers[subscription_id] = receiver

            # Start receiver task
            async def receive_loop() -> None:
                try:
                    async with receiver:
                        async for message in receiver:
                            try:
                                # Get event type from subject or properties
                                event_type = (
                                    message.subject
                                    or message.application_properties.get(
                                        "event_type",
                                        "Unknown",
                                    )
                                )

                                # Filter by event types
                                if event_types and event_type not in event_types:
                                    await receiver.complete_message(message)
                                    continue

                                # Deserialize and handle
                                body = (
                                    message.body
                                    if isinstance(message.body, bytes)
                                    else str(message.body).encode()
                                )
                                event = self.serializer.deserialize(body, event_type)

                                result = handler(event)
                                if asyncio.iscoroutine(result):
                                    await result

                                # Complete message
                                if not self.config.auto_complete:
                                    await receiver.complete_message(message)

                            except Exception as e:  # noqa: BLE001 — per-message handler isolation; abandon and continue
                                logger.exception(
                                    "Error processing message", error=str(e)
                                )
                                # Abandon for retry
                                await receiver.abandon_message(message)

                except asyncio.CancelledError:
                    pass
                except Exception as e:  # noqa: BLE001 — receiver loop background task; log and exit gracefully
                    logger.exception("Receiver loop error", error=str(e))

            from quadkit.concurrency.executors.task_manager import TaskManager

            task_manager = self._task_manager or TaskManager()
            task = task_manager.create_critical_task(
                receive_loop(),
                name=f"asb_receiver_{subscription_id}",
            )

            def _log_task_result(t: asyncio.Task) -> None:
                try:
                    # Avoid calling t.exception() directly. Mocks can trigger
                    # coroutine side-effects when t.exception() is accessed.
                    if t.cancelled():
                        return
                    if t.done():
                        logger.error(
                            "Receiver task completed with an exception",
                        )
                except (AttributeError, RuntimeError, ValueError):
                    with contextlib.suppress(OSError, ValueError, TypeError):
                        logger.exception("Error in receiver done-callback")

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
                        name=f"asb_callback_{subscription_id}",
                    )
            except (AttributeError, TypeError, ValueError):
                with contextlib.suppress(OSError, ValueError, TypeError):
                    logger.exception("Failed to register receiver callback")
            self._receiver_tasks[subscription_id] = task

            logger.info(
                "Subscribed to Azure Service Bus: %s (ID: %s)",
                subscription_name,
                subscription_id,
            )
            return subscription_id

        except (ConnectionError, RuntimeError, ValueError, TypeError) as e:
            logger.exception("Failed to subscribe")
            raise RuntimeError(f"Failed to subscribe: {e}") from e

    async def unsubscribe(self, subscription_id: str) -> None:
        """Unsubscribe from events.

        Args:
            subscription_id: ID of the subscription to cancel.
        """
        # Cancel task
        if subscription_id in self._receiver_tasks:
            task = self._receiver_tasks.pop(subscription_id)
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

        # Close receiver
        if subscription_id in self._receivers:
            receiver = self._receivers.pop(subscription_id)
            await receiver.close()
            logger.info("Unsubscribed from Azure Service Bus: %s", subscription_id)

    async def publish_batch(self, events: list[Event]) -> None:
        """Publish multiple events as a batch.

        Args:
            events: List of events to publish.
        """
        if not self._connected or not self._sender:
            raise RuntimeError("Not connected to Azure Service Bus")

        try:
            from azure.servicebus import (
                ServiceBusMessage,
            )

            messages = []
            for event in events:
                headers = self._create_headers(event)
                body = self.serializer.serialize(event)

                message = ServiceBusMessage(
                    body=body,
                    content_type="application/json",
                    subject=type(event).__name__,
                    application_properties=cast(
                        "dict[str | bytes, int | float | bytes | bool | str | UUID]",
                        headers.to_dict(),
                    ),
                )
                messages.append(message)

            await self._sender.send_messages(messages)
            logger.debug("Published batch of %d events", len(events))

        except (ConnectionError, RuntimeError, ValueError, TypeError) as e:
            logger.exception("Failed to publish batch")
            raise RuntimeError(f"Failed to publish batch: {e}") from e

    async def schedule_message(
        self,
        event: Event,
        scheduled_enqueue_time: Any,
    ) -> int:
        """Schedule an event for future delivery.

        Args:
            event: The event to schedule.
            scheduled_enqueue_time: When to deliver the event.

        Returns:
            Sequence number of scheduled message.
        """
        if not self._connected or not self._sender:
            raise RuntimeError("Not connected to Azure Service Bus")

        try:
            from azure.servicebus import (
                ServiceBusMessage,
            )

            headers = self._create_headers(event)
            body = self.serializer.serialize(event)

            message = ServiceBusMessage(
                body=body,
                content_type="application/json",
                subject=type(event).__name__,
                application_properties=cast(
                    "dict[str | bytes, int | float | bytes | bool | str | UUID]",
                    headers.to_dict(),
                ),
            )

            sequence_numbers = await self._sender.schedule_messages(
                message,
                scheduled_enqueue_time,
            )

            logger.debug(
                "Scheduled event %s for %s",
                type(event).__name__,
                scheduled_enqueue_time,
            )
            return int(sequence_numbers[0])

        except (ConnectionError, RuntimeError, ValueError, TypeError) as e:
            logger.exception("Failed to schedule message")
            raise RuntimeError(f"Failed to schedule message: {e}") from e

    async def cancel_scheduled_message(self, sequence_number: int) -> None:
        """Cancel a scheduled message.

        Args:
            sequence_number: Sequence number of the scheduled message.
        """
        if not self._connected or not self._sender:
            raise RuntimeError("Not connected to Azure Service Bus")

        await self._sender.cancel_scheduled_messages(sequence_number)
        logger.debug("Cancelled scheduled message: %s", sequence_number)
