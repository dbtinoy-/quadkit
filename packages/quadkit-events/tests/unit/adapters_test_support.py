"""Shared doubles for event-adapter tests."""

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


class _TestEvent(Event):
    """Test event for adapter testing."""

    data: str


class _TestMessageAdapter(MessageAdapter[_TestEvent]):
    """Test implementation of MessageAdapter."""

    def __init__(
        self, config: AdapterConfig, serializer: MessageSerializer | None = None,
    ):
        super().__init__(config, serializer)
        self.published_events: list[_TestEvent] = []
        self.subscriptions: dict[str, tuple[list[str], Callable]] = {}

    async def connect(self) -> None:
        self._connected = True

    async def disconnect(self) -> None:
        self._connected = False

    async def publish(self, event: _TestEvent) -> None:
        if not self._connected:
            raise ConnectionError("Not connected")
        self.published_events.append(event)

    async def subscribe(
        self,
        event_types: list[str],
        handler: Callable[[_TestEvent], Any],
    ) -> str:
        subscription_id = str(len(self.subscriptions))
        self.subscriptions[subscription_id] = (event_types, handler)
        return subscription_id

    async def unsubscribe(self, subscription_id: str) -> None:
        self.subscriptions.pop(subscription_id, None)


