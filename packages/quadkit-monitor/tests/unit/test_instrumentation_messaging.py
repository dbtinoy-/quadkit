"""Tests for messaging instrumentation."""

import pytest

pytest.importorskip("opentelemetry", reason="Requires opentelemetry")
from unittest.mock import MagicMock
from opentelemetry import metrics, trace

from quadkit.monitor.instrumentation.messaging import (
    trace_publish,
    trace_consume,
    inject_trace_context,
    _get_recipient_type,
)


def test_get_recipient_type():
    """Test recipient type detection."""
    assert _get_recipient_type("user@example.com") == "email"
    assert _get_recipient_type("+1234567890") == "phone"
    assert _get_recipient_type("device_token_xyz") == "device_token"


@pytest.mark.asyncio
async def test_trace_publish_success():
    """Test trace publish success."""
    async with trace_publish("channel1", "email", "user@example.com", extra_attr="value") as span:
        assert span is not None
        
@pytest.mark.asyncio
async def test_trace_publish_no_recipient():
    """Test trace publish without recipient."""
    async with trace_publish("channel2", "sms") as span:
        assert span is not None

@pytest.mark.asyncio
async def test_trace_publish_error():
    """Test trace publish error."""
    with pytest.raises(ValueError, match="publish error"):
        async with trace_publish("channel3", "push", "user@example.com"):
            raise ValueError("publish error")

@pytest.mark.asyncio
async def test_trace_consume_success():
    """Test trace consume success."""
    carrier = {"traceparent": "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"}
    async with trace_consume("channel1", "email", carrier, extra_attr="value") as span:
        assert span is not None

@pytest.mark.asyncio
async def test_trace_consume_no_carrier():
    """Test trace consume without carrier."""
    async with trace_consume("channel2", "sms") as span:
        assert span is not None

@pytest.mark.asyncio
async def test_trace_consume_error():
    """Test trace consume error."""
    with pytest.raises(ValueError, match="consume error"):
        async with trace_consume("channel3", "push"):
            raise ValueError("consume error")

def test_inject_trace_context():
    """Test inject trace context."""
    carrier = {}
    inject_trace_context(carrier)
    # the exact output depends on opentelemetry environment, we just ensure it doesn't crash
    assert isinstance(carrier, dict)
