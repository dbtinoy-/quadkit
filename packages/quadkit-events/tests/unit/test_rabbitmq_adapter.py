"""RabbitMQ adapter tests."""

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


class TestRabbitMQAdapter:
    """Test RabbitMQ adapter."""

    @pytest.fixture
    def config(self):
        """Create test config."""
        from quadkit.events.adapters.rabbitmq import RabbitMQAdapterConfig

        return RabbitMQAdapterConfig(
            connection_string="amqp://localhost/",
            exchange_name="test-events", # Changed from "test-exchange" to "test-events"
            routing_key_prefix="test.",
            timeout=10, # Added timeout
        )

    @pytest.fixture
    def adapter(self, config):
        """Create test adapter."""
        from quadkit.events.adapters.rabbitmq import RabbitMQAdapter

        return RabbitMQAdapter(config)

    @pytest.mark.asyncio
    async def test_connect_success(self, adapter, config):
        """Test successful connection."""
        mock_connection = AsyncMock()
        mock_channel = AsyncMock()
        mock_exchange = AsyncMock()

        mock_aio_pika = MagicMock()
        mock_aio_pika.connect_robust = mock_connect = AsyncMock(return_value=mock_connection)
        mock_aio_pika.ExchangeType.TOPIC = "topic"
        mock_connection.channel.return_value = mock_channel
        mock_channel.declare_exchange.return_value = mock_exchange

        with patch.dict("sys.modules", {"aio_pika": mock_aio_pika}):
            await adapter.connect()

            assert adapter.is_connected
            assert adapter._connection == mock_connection
            assert adapter._channel == mock_channel
            assert adapter._exchange == mock_exchange

    @pytest.mark.asyncio
    async def test_connect_failure(self, adapter):
        """Test connection failure."""
        mock_aio_pika = MagicMock()
        mock_aio_pika.connect_robust = AsyncMock(side_effect=Exception("Connection failed"))
        with patch.dict("sys.modules", {"aio_pika": mock_aio_pika}):
            with pytest.raises(AdapterConnectionError, match="RabbitMQ"):
                await adapter.connect()

    @pytest.mark.asyncio
    async def test_disconnect(self, adapter):
        """Test disconnecting."""
        mock_connection = AsyncMock()
        adapter._connection = mock_connection
        adapter._connected = True

        await adapter.disconnect()

        assert not adapter.is_connected
        mock_connection.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_success(self, adapter):
        """Test successful publishing."""
        adapter._connected = True
        mock_exchange = AsyncMock()
        adapter._exchange = mock_exchange

        event = _TestEvent(aggregate_id=uuid4(), data="test")

        mock_message_instance = MagicMock()
        mock_aio_pika = MagicMock()
        mock_aio_pika.Message = mock_message = MagicMock(return_value=mock_message_instance)
        mock_aio_pika.DeliveryMode.PERSISTENT = "persistent"

        with patch.dict("sys.modules", {"aio_pika": mock_aio_pika}):
            await adapter.publish(event)

            mock_message.assert_called_once()
            mock_exchange.publish.assert_called_once_with(
                mock_message_instance, routing_key="test._TestEvent",
            )

    @pytest.mark.asyncio
    async def test_publish_not_connected(self, adapter):
        """Test publishing when not connected."""
        event = _TestEvent(aggregate_id=uuid4(), data="test")

        with pytest.raises(RuntimeError, match="Not connected to RabbitMQ"):
            await adapter.publish(event)

    @pytest.mark.asyncio
    async def test_subscribe_success(self, adapter, config):
        """Test successful subscription."""
        adapter._connected = True
        mock_channel = AsyncMock()
        mock_exchange = AsyncMock()
        mock_queue = AsyncMock()
        adapter._channel = mock_channel
        adapter._exchange = mock_exchange
        mock_channel.declare_queue.return_value = mock_queue

        subscription_id = await adapter.subscribe(["TestEvent"], MagicMock())

        assert subscription_id in adapter._subscriptions
        sub = adapter._subscriptions[subscription_id]
        assert sub["queue"] == mock_queue
        assert sub["event_types"] == ["TestEvent"]
        mock_channel.declare_queue.assert_called_once()
        mock_queue.bind.assert_called_once_with(
            mock_exchange, routing_key="test.TestEvent",
        )
        mock_queue.consume.assert_called_once()

    @pytest.mark.asyncio
    async def test_subscribe_not_connected(self, adapter):
        """Test subscribing when not connected."""
        with pytest.raises(RuntimeError, match="Not connected to RabbitMQ"):
            await adapter.subscribe(["TestEvent"], MagicMock())

    @pytest.mark.asyncio
    async def test_unsubscribe(self, adapter):
        """Test unsubscribing."""
        mock_queue = AsyncMock()
        subscription_id = "test-sub"
        adapter._subscriptions[subscription_id] = {
            "queue": mock_queue,
            "consumer_tag": "tag123",
            "event_types": ["TestEvent"],
        }

        await adapter.unsubscribe(subscription_id)

        assert subscription_id not in adapter._subscriptions
        mock_queue.cancel.assert_called_once_with("tag123")

    @pytest.mark.asyncio
    async def test_publish_batch(self, adapter):
        """Test publishing batch of events."""
        adapter._connected = True
        mock_exchange = AsyncMock()
        adapter._exchange = mock_exchange

        events = [
            _TestEvent(aggregate_id=uuid4(), data="test1"),
            _TestEvent(aggregate_id=uuid4(), data="test2"),
        ]

        mock_message_instances = [MagicMock(), MagicMock()]
        mock_aio_pika = MagicMock()
        mock_aio_pika.Message = mock_message = MagicMock(side_effect=mock_message_instances)
        mock_aio_pika.DeliveryMode.PERSISTENT = "persistent"

        with patch.dict("sys.modules", {"aio_pika": mock_aio_pika}):
            await adapter.publish_batch(events)

            assert mock_message.call_count == 2
            assert mock_exchange.publish.call_count == 2
