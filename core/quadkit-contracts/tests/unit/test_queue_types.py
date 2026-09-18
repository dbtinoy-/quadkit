"""Tests for queue types."""

from __future__ import annotations

import time
from dataclasses import replace

from quadkit.contracts.queue.types import BusMessage, DeliveryGuarantee


class TestDeliveryGuarantee:
    """Tests for DeliveryGuarantee enum."""

    def test_values(self) -> None:
        """Test DeliveryGuarantee enum values."""
        assert DeliveryGuarantee.AT_MOST_ONCE.value == "at_most_once"
        assert DeliveryGuarantee.AT_LEAST_ONCE.value == "at_least_once"
        assert DeliveryGuarantee.EXACTLY_ONCE.value == "exactly_once"

    def test_is_str_enum(self) -> None:
        """Test DeliveryGuarantee is a StrEnum."""
        assert isinstance(DeliveryGuarantee.AT_MOST_ONCE.value, str)


class TestBusMessage:
    """Tests for BusMessage."""

    def test_creation_defaults(self) -> None:
        """Test BusMessage with default values."""
        msg = BusMessage(topic="test-topic", payload={"key": "value"})
        assert msg.id is not None
        assert msg.topic == "test-topic"
        assert msg.payload == {"key": "value"}
        assert msg.headers == {}
        assert msg.timestamp is not None
        assert msg.ttl is None
        assert msg.priority == 0
        assert msg.delivery_guarantee == DeliveryGuarantee.AT_LEAST_ONCE
        assert msg.retry_count == 0
        assert msg.max_retries == 3

    def test_custom_values(self) -> None:
        """Test BusMessage with custom values."""
        msg = BusMessage(
            id="msg-123",
            topic="orders",
            payload={"order_id": "123"},
            headers={"x-correlation-id": "abc"},
            ttl=300,
            priority=10,
            delivery_guarantee=DeliveryGuarantee.EXACTLY_ONCE,
            retry_count=1,
            max_retries=5,
        )
        assert msg.id == "msg-123"
        assert msg.topic == "orders"
        assert msg.headers == {"x-correlation-id": "abc"}
        assert msg.ttl == 300
        assert msg.priority == 10
        assert msg.delivery_guarantee == DeliveryGuarantee.EXACTLY_ONCE
        assert msg.retry_count == 1
        assert msg.max_retries == 5

    def test_is_expired_no_ttl(self) -> None:
        """Test is_expired returns False when no TTL."""
        msg = BusMessage(topic="test", payload={})
        assert msg.is_expired() is False

    def test_is_expired_not_expired(self) -> None:
        """Test is_expired returns False when not expired."""
        msg = BusMessage(topic="test", payload={}, ttl=3600)  # 1 hour
        assert msg.is_expired() is False

    def test_is_expired_expired(self) -> None:
        """Test is_expired returns True when expired."""
        msg = BusMessage(topic="test", payload={}, ttl=0)  # Already expired
        # Create new instance with past timestamp to test expiration
        msg = replace(msg, timestamp=time.time() - 100, ttl=10)
        assert msg.is_expired() is True

    def test_should_retry_true(self) -> None:
        """Test should_retry returns True when can retry."""
        msg = BusMessage(topic="test", payload={}, retry_count=0, max_retries=3)
        assert msg.should_retry() is True

    def test_should_retry_max_retries_exceeded(self) -> None:
        """Test should_retry returns False when max retries exceeded."""
        msg = BusMessage(topic="test", payload={}, retry_count=3, max_retries=3)
        assert msg.should_retry() is False

    def test_should_retry_expired(self) -> None:
        """Test should_retry returns False when message expired."""
        msg = BusMessage(topic="test", payload={}, retry_count=0, max_retries=3, ttl=0)
        msg = replace(msg, timestamp=time.time() - 100)
        assert msg.should_retry() is False

    def test_uuid_generated(self) -> None:
        """Test ID is a valid UUID string."""
        msg = BusMessage(topic="test", payload={})
        # Should be a valid UUID string
        assert len(msg.id) == 36  # UUID format


class TestBusMessageIntegration:
    """Integration tests for BusMessage."""

    def test_can_encode_payload(self) -> None:
        """Test payload can be various types."""
        msg = BusMessage(topic="test", payload={"key": "value"})
        assert msg.payload == {"key": "value"}

    def test_can_use_with_headers(self) -> None:
        """Test message with headers."""
        msg = BusMessage(
            topic="orders",
            payload={"data": "test"},
            headers={
                "content-type": "application/json",
                "x-request-id": "req-123",
            },
        )
        assert len(msg.headers) == 2

    def test_can_chain_retry(self) -> None:
        """Test retry count increments."""
        msg = BusMessage(topic="test", payload={}, retry_count=0, max_retries=3)
        assert msg.should_retry() is True

        msg = replace(msg, retry_count=2)
        assert msg.should_retry() is True

        msg = replace(msg, retry_count=3)
        assert msg.should_retry() is False
