"""Azure Service Bus adapter tests."""

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from quadkit.events.exceptions import AdapterConnectionError

from quadkit.events.adapters.base import (
    AdapterConfig,
    DefaultMessageSerializer,
    MessageAdapter,
    MessageHeaders,
    MessageSerializer,
)
from quadkit.events.messages.event import Event

from adapters_test_support import _TestEvent, _TestMessageAdapter


class TestAzureServiceBusAdapter:
    """Test Azure Service Bus adapter."""

    @pytest.fixture
    def config(self):
        """Create test config."""
        from quadkit.events.adapters.azure_servicebus import AzureServiceBusAdapterConfig

        return AzureServiceBusAdapterConfig(
            connection_string="test-connection-string",
            topic_name="test-topic",
            subscription_name="test-subscription",
        )

    @pytest.fixture
    def adapter(self, config):
        """Create test adapter."""
        from quadkit.events.adapters.azure_servicebus import AzureServiceBusAdapter

        return AzureServiceBusAdapter(config)

    @pytest.mark.asyncio
    async def test_connect_success(self, adapter, config):
        """Test successful connection."""
        mock_client = AsyncMock()
        mock_sender = AsyncMock()

        with patch(
            "azure.servicebus.aio.ServiceBusClient.from_connection_string",
        ) as mock_from_conn:
            mock_from_conn.return_value = mock_client
            mock_client.get_topic_sender = AsyncMock(return_value=mock_sender)

            await adapter.connect()

            assert adapter.is_connected
            assert adapter._client == mock_client
            assert adapter._sender == mock_sender
            mock_from_conn.assert_called_once_with(config.connection_string.get_secret_value())
            mock_client.get_topic_sender.assert_called_once_with(
                topic_name=config.topic_name,
            )

    @pytest.mark.asyncio
    async def test_connect_failure(self, adapter):
        """Test connection failure."""
        with patch(
            "azure.servicebus.aio.ServiceBusClient.from_connection_string",
            side_effect=Exception("Connection failed"),
        ):
            with pytest.raises(
                AdapterConnectionError, match="Azure Service Bus",
            ):
                await adapter.connect()

    @pytest.mark.asyncio
    async def test_disconnect(self, adapter):
        """Test disconnecting."""
        mock_client = AsyncMock()
        mock_sender = AsyncMock()
        adapter._client = mock_client
        adapter._sender = mock_sender
        adapter._connected = True

        await adapter.disconnect()

        assert not adapter.is_connected
        mock_sender.close.assert_called_once()
        mock_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_success(self, adapter):
        """Test successful publishing."""
        adapter._connected = True
        mock_sender = AsyncMock()
        adapter._sender = mock_sender

        event = _TestEvent(aggregate_id=uuid4(), data="test")

        with patch("azure.servicebus.ServiceBusMessage") as mock_message:
            mock_message_instance = MagicMock()
            mock_message.return_value = mock_message_instance

            await adapter.publish(event)

            mock_message.assert_called_once()
            mock_sender.send_messages.assert_called_once_with(mock_message_instance)

    @pytest.mark.asyncio
    async def test_publish_not_connected(self, adapter):
        """Test publishing when not connected."""
        event = _TestEvent(aggregate_id=uuid4(), data="test")

        with pytest.raises(RuntimeError, match="Not connected to Azure Service Bus"):
            await adapter.publish(event)

    @pytest.mark.asyncio
    async def test_subscribe_success(self, adapter, config):
        """Test successful subscription."""
        adapter._connected = True
        mock_client = AsyncMock()
        mock_receiver = AsyncMock()
        adapter._client = mock_client
        mock_client.get_subscription_receiver = AsyncMock(return_value=mock_receiver)

        handler = MagicMock()

        with patch("asyncio.create_task") as mock_create_task:
            mock_task = AsyncMock()
            # Ensure add_done_callback is a regular callable in tests so it doesn't return an un-awaited coroutine
            mock_task.add_done_callback = MagicMock()
            coro_holder: dict[str, object] = {}

            def _fake_create_task(coro, **kwargs):
                coro_holder["coro"] = coro
                return mock_task

            mock_create_task.side_effect = _fake_create_task
            subscription_id = await adapter.subscribe(["TestEvent"], handler)

            # Close the created coroutine to avoid 'coroutine was never awaited' warnings from test harness
            if "coro" in coro_holder:
                try:
                    coro_holder["coro"].close()
                except RuntimeError:
                    pass

            assert subscription_id in adapter._receivers
            assert subscription_id in adapter._receiver_tasks
            assert adapter._receivers[subscription_id] == mock_receiver
            assert adapter._receiver_tasks[subscription_id] == mock_task
            mock_create_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_subscribe_not_connected(self, adapter):
        """Test subscribing when not connected."""
        handler = MagicMock()

        with pytest.raises(RuntimeError, match="Not connected to Azure Service Bus"):
            await adapter.subscribe(["TestEvent"], handler)

    @pytest.mark.asyncio
    async def test_unsubscribe(self, adapter):
        """Test unsubscribing."""
        mock_receiver = AsyncMock()

        # Create a real task that can be cancelled
        task = asyncio.create_task(asyncio.sleep(0))

        subscription_id = "test-sub"

        adapter._receivers[subscription_id] = mock_receiver
        adapter._receiver_tasks[subscription_id] = task

        await adapter.unsubscribe(subscription_id)

        assert subscription_id not in adapter._receivers
        assert subscription_id not in adapter._receiver_tasks
        assert task.cancelled()
        mock_receiver.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_batch(self, adapter):
        """Test publishing batch of events."""
        adapter._connected = True
        mock_sender = AsyncMock()
        adapter._sender = mock_sender

        events = [
            _TestEvent(aggregate_id=uuid4(), data="test1"),
            _TestEvent(aggregate_id=uuid4(), data="test2"),
        ]

        with patch("azure.servicebus.ServiceBusMessage") as mock_message:
            mock_message_instances = [MagicMock(), MagicMock()]
            mock_message.side_effect = mock_message_instances

            await adapter.publish_batch(events)

            assert mock_message.call_count == 2
            mock_sender.send_messages.assert_called_once_with(mock_message_instances)

    @pytest.mark.asyncio
    async def test_schedule_message(self, adapter):
        """Test scheduling a message."""
        adapter._connected = True
        mock_sender = AsyncMock()
        adapter._sender = mock_sender
        mock_sender.schedule_messages.return_value = [12345]

        event = _TestEvent(aggregate_id=uuid4(), data="test")
        scheduled_time = datetime.now(UTC)

        with patch("azure.servicebus.ServiceBusMessage") as mock_message:
            mock_message_instance = MagicMock()
            mock_message.return_value = mock_message_instance

            result = await adapter.schedule_message(event, scheduled_time)

            assert result == 12345
            mock_sender.schedule_messages.assert_called_once()

    @pytest.mark.asyncio
    async def test_cancel_scheduled_message(self, adapter):
        """Test canceling a scheduled message."""
        adapter._connected = True
        mock_sender = AsyncMock()
        adapter._sender = mock_sender

        await adapter.cancel_scheduled_message(12345)

        mock_sender.cancel_scheduled_messages.assert_called_once_with(12345)


