"""Adapter config, headers, serializer, and base-adapter tests."""

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


class TestAdapterConfig:
    """Test AdapterConfig functionality."""

    def test_default_config(self):
        """Test default configuration values."""
        config = AdapterConfig()
        assert config.connection_string == ""
        assert config.timeout == 30.0
        assert config.reconnect_attempts == 3
        assert config.reconnect_delay == 1.0
        assert config.enable_logging is True

    def test_custom_config(self):
        """Test custom configuration values."""
        config = AdapterConfig(
            connection_string="test://",
            timeout=60.0,
            reconnect_attempts=5,
            reconnect_delay=2.0,
            enable_logging=False,
        )
        assert config.connection_string == "test://"
        assert config.timeout == 60.0
        assert config.reconnect_attempts == 5
        assert config.reconnect_delay == 2.0
        assert config.enable_logging is False


class TestMessageHeaders:
    """Test MessageHeaders functionality."""

    def test_default_headers(self):
        """Test default header creation."""
        headers = MessageHeaders(event_type="TestEvent")
        assert headers.event_type == "TestEvent"
        assert headers.aggregate_id is None
        assert headers.aggregate_type is None
        assert headers.correlation_id is None
        assert headers.causation_id is None
        assert headers.metadata == {}
        assert isinstance(headers.timestamp, datetime)

    def test_full_headers(self):
        """Test headers with all fields."""
        timestamp = datetime.now(UTC)
        headers = MessageHeaders(
            event_type="OrderCreated",
            aggregate_id="order-123",
            aggregate_type="Order",
            timestamp=timestamp,
            correlation_id="corr-456",
            causation_id="cause-789",
            metadata={"key": "value"},
        )
        assert headers.event_type == "OrderCreated"
        assert headers.aggregate_id == "order-123"
        assert headers.aggregate_type == "Order"
        assert headers.timestamp == timestamp
        assert headers.correlation_id == "corr-456"
        assert headers.causation_id == "cause-789"
        assert headers.metadata == {"key": "value"}

    def test_to_dict(self):
        """Test converting headers to dictionary."""
        timestamp = datetime(2023, 1, 1, 12, 0, 0, tzinfo=UTC)
        headers = MessageHeaders(
            event_type="TestEvent",
            aggregate_id="agg-123",
            aggregate_type="TestAggregate",
            timestamp=timestamp,
            correlation_id="corr-456",
            causation_id="cause-789",
            metadata={"env": "test"},
        )
        result = headers.to_dict()
        expected = {
            "event_type": "TestEvent",
            "aggregate_id": "agg-123",
            "aggregate_type": "TestAggregate",
            "timestamp": "2023-01-01T12:00:00+00:00",
            "correlation_id": "corr-456",
            "causation_id": "cause-789",
            "env": "test",
        }
        assert result == expected

    def test_from_dict(self):
        """Test creating headers from dictionary."""
        data = {
            "event_type": "TestEvent",
            "aggregate_id": "agg-123",
            "aggregate_type": "TestAggregate",
            "timestamp": "2023-01-01T12:00:00+00:00",
            "correlation_id": "corr-456",
            "causation_id": "cause-789",
            "custom": "value",
        }
        headers = MessageHeaders.from_dict(data)
        assert headers.event_type == "TestEvent"
        assert headers.aggregate_id == "agg-123"
        assert headers.aggregate_type == "TestAggregate"
        assert headers.correlation_id == "corr-456"
        assert headers.causation_id == "cause-789"
        assert headers.metadata == {"custom": "value"}

    def test_from_dict_minimal(self):
        """Test creating headers from minimal dictionary."""
        data = {"event_type": "TestEvent"}
        headers = MessageHeaders.from_dict(data)
        assert headers.event_type == "TestEvent"
        assert headers.aggregate_id is None
        assert headers.metadata == {}


class TestDefaultMessageSerializer:
    """Test DefaultMessageSerializer functionality."""

    def test_initialization(self):
        """Test serializer initialization."""
        serializer = DefaultMessageSerializer()
        assert serializer._event_types == {}

    def test_register_event_type(self):
        """Test registering a single event type."""
        serializer = DefaultMessageSerializer()
        serializer.register_event_type(_TestEvent)
        assert serializer._event_types == {"_TestEvent": _TestEvent}

    def test_register_event_types(self):
        """Test registering multiple event types."""
        serializer = DefaultMessageSerializer()
        serializer.register_event_types(_TestEvent)
        assert serializer._event_types == {"_TestEvent": _TestEvent}

    def test_serialize_pydantic_event(self):
        """Test serializing a Pydantic event."""
        serializer = DefaultMessageSerializer()
        event = _TestEvent(aggregate_id=uuid4(), data="test data")
        data = serializer.serialize(event)
        assert isinstance(data, bytes)
        # Should contain JSON data
        json_str = data.decode()
        assert "test data" in json_str

    def test_deserialize_registered_event(self):
        """Test deserializing a registered event."""
        serializer = DefaultMessageSerializer()
        serializer.register_event_type(_TestEvent)

        event = _TestEvent(aggregate_id=uuid4(), data="test data")
        data = serializer.serialize(event)
        deserialized = serializer.deserialize(data, "_TestEvent")

        assert isinstance(deserialized, _TestEvent)
        assert deserialized.data == "test data"

    def test_deserialize_unregistered_event(self):
        """Test deserializing an unregistered event raises error."""
        serializer = DefaultMessageSerializer()
        data = b'{"event_type": "UnknownEvent"}'

        with pytest.raises(ValueError, match="Unknown event type: UnknownEvent"):
            serializer.deserialize(data, "UnknownEvent")


class TestMessageAdapter:
    """Test MessageAdapter base functionality."""

    def test_initialization(self):
        """Test adapter initialization."""
        config = AdapterConfig()
        adapter = _TestMessageAdapter(config)

        assert adapter.config == config
        assert isinstance(adapter.serializer, DefaultMessageSerializer)
        assert not adapter.is_connected

    def test_initialization_with_serializer(self):
        """Test adapter initialization with custom serializer."""
        config = AdapterConfig()
        serializer = DefaultMessageSerializer()
        adapter = _TestMessageAdapter(config, serializer)

        assert adapter.serializer == serializer

    @pytest.mark.asyncio
    async def test_connect_disconnect(self):
        """Test connecting and disconnecting."""
        adapter = _TestMessageAdapter(AdapterConfig())

        await adapter.connect()
        assert adapter.is_connected

        await adapter.disconnect()
        assert not adapter.is_connected

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async context manager."""
        adapter = _TestMessageAdapter(AdapterConfig())

        async with adapter:
            assert adapter.is_connected

        assert not adapter.is_connected

    @pytest.mark.asyncio
    async def test_publish_when_connected(self):
        """Test publishing when connected."""
        adapter = _TestMessageAdapter(AdapterConfig())
        await adapter.connect()

        event = _TestEvent(aggregate_id=uuid4(), data="test")
        await adapter.publish(event)

        assert len(adapter.published_events) == 1
        assert adapter.published_events[0] == event

    @pytest.mark.asyncio
    async def test_publish_when_disconnected(self):
        """Test publishing when disconnected raises error."""
        adapter = _TestMessageAdapter(AdapterConfig())
        event = _TestEvent(aggregate_id=uuid4(), data="test")

        with pytest.raises(ConnectionError, match="Not connected"):
            await adapter.publish(event)

    @pytest.mark.asyncio
    async def test_subscribe_unsubscribe(self):
        """Test subscribing and unsubscribing."""
        adapter = _TestMessageAdapter(AdapterConfig())
        handler = MagicMock()

        # Subscribe
        subscription_id = await adapter.subscribe(["TestEvent"], handler)
        assert subscription_id in adapter.subscriptions
        assert adapter.subscriptions[subscription_id] == (["TestEvent"], handler)

        # Unsubscribe
        await adapter.unsubscribe(subscription_id)
        assert subscription_id not in adapter.subscriptions

    def test_create_headers(self):
        """Test creating headers from event."""
        adapter = _TestMessageAdapter(AdapterConfig())
        event = _TestEvent(aggregate_id=uuid4(), data="test")

        headers = adapter._create_headers(event)
        assert headers.event_type == "_TestEvent"


