"""Contract compliance suite for ``EventBusProtocol`` implementations.

Subclass :class:`EventBusCompliance` and implement
:meth:`create_bus` and :meth:`create_event`::

    from quadkit.testing.compliance import EventBusCompliance

    class TestInMemoryEventBus(EventBusCompliance):
        async def create_bus(self):
            return InMemoryEventBus()

        def create_event(self):
            return UserCreated(user_id="u1")
"""

from __future__ import annotations

from abc import abstractmethod
from typing import Any

import pytest

__all__ = ["EventBusCompliance"]


class EventBusCompliance:
    """Reusable test suite for any ``EventBusProtocol`` implementation.

    Subclass and implement :meth:`create_bus` and :meth:`create_event`:

    .. code-block:: python

        class TestMyEventBus(EventBusCompliance):
            async def create_bus(self):
                return MyEventBus()

            def create_event(self):
                return MyEvent(id="1")
    """

    @abstractmethod
    async def create_bus(self) -> Any:
        """Return a fresh EventBusProtocol instance."""
        ...

    @abstractmethod
    def create_event(self) -> Any:
        """Return a new event instance for testing."""
        ...

    # ------------------------------------------------------------------
    # Core contract tests
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_subscribe_and_publish(self) -> None:
        """Subscribing a handler causes it to be called on publish."""
        bus = await self.create_bus()
        received: list[Any] = []
        event = self.create_event()
        event_type = type(event)

        async def handler(e: Any) -> None:
            received.append(e)

        bus.subscribe(event_type, handler)
        await bus.publish(event)

        assert len(received) == 1
        assert received[0] is event

    @pytest.mark.asyncio
    async def test_unsubscribe_stops_delivery(self) -> None:
        """Unsubscribing a handler prevents further delivery."""
        bus = await self.create_bus()
        received: list[Any] = []
        event = self.create_event()
        event_type = type(event)

        async def handler(e: Any) -> None:
            received.append(e)

        bus.subscribe(event_type, handler)
        bus.unsubscribe(event_type, handler)
        await bus.publish(event)

        assert received == []

    @pytest.mark.asyncio
    async def test_multiple_handlers_all_called(self) -> None:
        """All subscribers for an event type are invoked."""
        bus = await self.create_bus()
        calls: list[str] = []
        event = self.create_event()
        event_type = type(event)

        async def handler_a(e: Any) -> None:
            calls.append("a")

        async def handler_b(e: Any) -> None:
            calls.append("b")

        bus.subscribe(event_type, handler_a)
        bus.subscribe(event_type, handler_b)
        await bus.publish(event)

        assert "a" in calls
        assert "b" in calls

    @pytest.mark.asyncio
    async def test_publish_unrelated_event_type_not_delivered(self) -> None:
        """A handler subscribed to one type does not receive another type."""

        class AnotherEvent:
            pass

        bus = await self.create_bus()
        received: list[Any] = []

        async def handler(e: Any) -> None:
            received.append(e)

        bus.subscribe(type(self.create_event()), handler)
        await bus.publish(AnotherEvent())

        assert received == []

    @pytest.mark.asyncio
    async def test_publish_without_subscribers_is_silent(self) -> None:
        """Publishing when there are no subscribers does not raise."""
        bus = await self.create_bus()
        event = self.create_event()
        await bus.publish(event)  # should not raise
