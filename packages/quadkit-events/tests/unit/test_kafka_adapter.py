"""Kafka adapter tests."""

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


class TestKafkaAdapter:
    """Test Kafka adapter."""

    @pytest.fixture
    def config(self):
        """Create test config."""
        from quadkit.events.adapters.kafka import KafkaAdapterConfig

        return KafkaAdapterConfig(
            connection_string="localhost:9092",
            topic_prefix="test.",
            group_id="test-group",
        )

    @pytest.fixture
    def adapter(self, config):
        """Create test adapter."""
        from quadkit.events.adapters.kafka import KafkaAdapter

        return KafkaAdapter(config)

    @pytest.mark.asyncio
    async def test_connect_success(self, adapter, config):
        """Test successful connection."""
        mock_producer = AsyncMock()

        mock_aiokafka = MagicMock()
        mock_aiokafka.AIOKafkaProducer = mock_producer_class = MagicMock(return_value=mock_producer)

        with patch.dict("sys.modules", {"aiokafka": mock_aiokafka}):
            await adapter.connect()

            assert adapter.is_connected
            assert adapter._producer == mock_producer
            mock_producer_class.assert_called_once()
            mock_producer.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_failure(self, adapter):
        """Test connection failure."""
        from quadkit.events.exceptions import AdapterConnectionError
        mock_aiokafka = MagicMock()
        mock_aiokafka.AIOKafkaProducer = MagicMock(side_effect=Exception("Connection failed"))
        with patch.dict("sys.modules", {"aiokafka": mock_aiokafka}):
            with pytest.raises(AdapterConnectionError, match="Kafka"):
                await adapter.connect()

    @pytest.mark.asyncio
    async def test_disconnect(self, adapter):
        """Test disconnecting."""
        mock_producer = AsyncMock()
        adapter._producer = mock_producer
        adapter._connected = True

        await adapter.disconnect()

        assert not adapter.is_connected
        mock_producer.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_success(self, adapter):
        """Test successful publishing."""
        adapter._connected = True
        mock_producer = AsyncMock()
        adapter._producer = mock_producer

        event = _TestEvent(aggregate_id=uuid4(), data="test")

        await adapter.publish(event)

        mock_producer.send_and_wait.assert_called_once()
        call_args = mock_producer.send_and_wait.call_args
        assert call_args[1]["topic"] == "test._TestEvent"
        assert call_args[1]["key"] == str(event.aggregate_id).encode()

    @pytest.mark.asyncio
    async def test_publish_not_connected(self, adapter):
        """Test publishing when not connected."""
        event = _TestEvent(aggregate_id=uuid4(), data="test")

        with pytest.raises(RuntimeError, match="Not connected to Kafka"):
            await adapter.publish(event)

    @pytest.mark.asyncio
    async def test_subscribe_success(self, adapter, config):
        """Test successful subscription."""
        adapter._connected = True
        mock_consumer = AsyncMock()

        mock_aiokafka = MagicMock()
        mock_aiokafka.AIOKafkaConsumer = mock_consumer_class = MagicMock(return_value=mock_consumer)

        with patch.dict("sys.modules", {"aiokafka": mock_aiokafka}):
            with patch("asyncio.create_task") as mock_create_task:
                mock_task = AsyncMock()
                # Ensure add_done_callback is a regular callable in tests so it doesn't return an un-awaited coroutine
                mock_task.add_done_callback = MagicMock()
                coro_holder: dict[str, object] = {}

                def _fake_create_task(coro, **kwargs):
                    coro_holder["coro"] = coro
                    return mock_task

                mock_create_task.side_effect = _fake_create_task

                subscription_id = await adapter.subscribe(["TestEvent"], MagicMock())

                # Close the created coroutine to avoid 'coroutine was never awaited' warnings from test harness
                if "coro" in coro_holder:
                    try:
                        coro_holder["coro"].close()
                    except RuntimeError:
                        pass

                assert subscription_id in adapter._consumers
                assert subscription_id in adapter._consumer_tasks
                assert adapter._consumers[subscription_id] == mock_consumer
                assert adapter._consumer_tasks[subscription_id] == mock_task
                mock_consumer.start.assert_called_once()
                mock_create_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_subscribe_not_connected(self, adapter):
        """Test subscribing when not connected."""
        with pytest.raises(RuntimeError, match="Not connected to Kafka"):
            await adapter.subscribe(["TestEvent"], MagicMock())

    @pytest.mark.asyncio
    async def test_unsubscribe(self, adapter):
        """Test unsubscribing."""
        mock_consumer = AsyncMock()

        task = asyncio.create_task(asyncio.sleep(0))

        subscription_id = "test-sub"

        adapter._consumers[subscription_id] = mock_consumer
        adapter._consumer_tasks[subscription_id] = task

        await adapter.unsubscribe(subscription_id)

        assert subscription_id not in adapter._consumers
        assert subscription_id not in adapter._consumer_tasks
        mock_consumer.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_batch(self, adapter):
        """Test publishing batch of events."""
        adapter._connected = True
        mock_producer = AsyncMock()
        adapter._producer = mock_producer

        events = [
            _TestEvent(aggregate_id=uuid4(), data="test1"),
            _TestEvent(aggregate_id=uuid4(), data="test2"),
        ]

        await adapter.publish_batch(events)

        assert mock_producer.send_and_wait.call_count == 2

    @pytest.mark.asyncio
    async def test_get_topic_partitions(self, adapter):
        """Test getting topic partitions."""
        adapter._connected = True
        mock_producer = AsyncMock()
        mock_producer.partitions_for.return_value = {0, 1, 2}
        adapter._producer = mock_producer

        partitions = await adapter.get_topic_partitions("test-topic")

        assert partitions == [0, 1, 2]
        mock_producer.partitions_for.assert_called_once_with("test-topic")


