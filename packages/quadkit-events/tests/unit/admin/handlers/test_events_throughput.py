"""Tests for the events_throughput admin widget handler."""

from __future__ import annotations

from unittest.mock import MagicMock

from quadkit.contracts.admin import MessageContent, Tone, WidgetParams
from quadkit.events.admin.handlers.events_throughput import (
    EventsThroughputWidgetHandler,
)


async def test_events_throughput_handler_returns_message_content() -> None:
    result = await EventsThroughputWidgetHandler(event_bus=MagicMock()).get_data(
        WidgetParams()
    )
    content = result.unwrap()
    assert isinstance(content, MessageContent)
    assert "not available" in content.text
    assert content.tone is Tone.DEFAULT


__all__ = ["test_events_throughput_handler_returns_message_content"]