"""Tests for the in-memory event bus (memory/event_bus.py)."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from quadkit.contracts.domain.events import DomainEvent
from quadkit.testing.memory.event_bus import InMemoryEventBus


class OrderCreated(DomainEvent):
    order_id: str = ""


class PaymentReceived(DomainEvent):
    amount: int = 0


class Handler:
    """Object-style handler (has a ``handle`` method)."""

    def __init__(self, log: list[str], tag: str) -> None:
        self.log = log
        self.tag = tag
        self.calls: list[Any] = []

    async def handle(self, event: DomainEvent) -> None:
        self.log.append(self.tag)
        self.calls.append(event)


class TestInMemoryEventBus:
    @pytest.mark.asyncio
    async def test_publish_dispatches_subscribed_handler(self) -> None:
        bus = InMemoryEventBus()
        handler = Handler(log := [], "h1")
        bus.subscribe(OrderCreated, handler)
        event = OrderCreated(order_id="o1")
        await bus.publish(event)
        assert log == ["h1"]
        assert handler.calls == [event]

    @pytest.mark.asyncio
    async def test_unsubscribed_type_receives_nothing(self) -> None:
        bus = InMemoryEventBus()
        log: list[str] = []
        bus.subscribe(OrderCreated, Handler(log, "h1"))
        await bus.publish(PaymentReceived(amount=5))
        assert log == []

    @pytest.mark.asyncio
    async def test_handlers_run_in_priority_order(self) -> None:
        bus = InMemoryEventBus()
        log: list[str] = []
        bus.subscribe(OrderCreated, Handler(log, "low"), priority=20)
        bus.subscribe(OrderCreated, Handler(log, "high"), priority=1)
        bus.subscribe(OrderCreated, Handler(log, "mid"), priority=10)
        await bus.publish(OrderCreated(order_id="o1"))
        assert log == ["high", "mid", "low"]

    @pytest.mark.asyncio
    async def test_same_priority_runs_in_registration_order(self) -> None:
        bus = InMemoryEventBus()
        log: list[str] = []
        bus.subscribe(OrderCreated, Handler(log, "first"), priority=5)
        bus.subscribe(OrderCreated, Handler(log, "second"), priority=5)
        await bus.publish(OrderCreated(order_id="o1"))
        assert log == ["first", "second"]

    @pytest.mark.asyncio
    async def test_wildcard_receives_all_event_types(self) -> None:
        bus = InMemoryEventBus()
        log: list[str] = []
        bus.subscribe("*", Handler(log, "wild"), priority=0)
        bus.subscribe(OrderCreated, Handler(log, "exact"), priority=0)
        await bus.publish(OrderCreated(order_id="o1"))
        await bus.publish(PaymentReceived(amount=5))
        # Exact-type handlers run before wildcards for matching types.
        assert log == ["exact", "wild", "wild"]

    @pytest.mark.asyncio
    async def test_unsubscribe_removes_handler(self) -> None:
        bus = InMemoryEventBus()
        handler = Handler(log := [], "h1")
        bus.subscribe(OrderCreated, handler)
        bus.unsubscribe(OrderCreated, handler)
        await bus.publish(OrderCreated(order_id="o1"))
        assert log == []

    @pytest.mark.asyncio
    async def test_unsubscribe_is_noop_for_unknown(self) -> None:
        bus = InMemoryEventBus()
        handler = Handler([], "h1")
        bus.unsubscribe(OrderCreated, handler)
        bus.unsubscribe("*", handler)
        assert bus.subscriber_count == 0

    @pytest.mark.asyncio
    async def test_plain_callable_handler_is_supported(self) -> None:
        bus = InMemoryEventBus()
        seen: list[Any] = []

        async def handler(event: DomainEvent) -> None:
            seen.append(event)

        bus.subscribe(OrderCreated, handler)
        await bus.publish(OrderCreated(order_id="o1"))
        assert len(seen) == 1
        assert seen[0].order_id == "o1"

    @pytest.mark.asyncio
    async def test_middleware_wraps_dispatch_in_order_added(self) -> None:
        bus = InMemoryEventBus()
        log: list[str] = []
        bus.subscribe(OrderCreated, Handler(log, "handler"))

        async def first(event: DomainEvent, nxt: Any) -> Any:
            log.append("first-before")
            result = await nxt(event)
            log.append("first-after")
            return result

        async def second(event: DomainEvent, nxt: Any) -> Any:
            log.append("second-before")
            result = await nxt(event)
            log.append("second-after")
            return result

        bus.add_middleware(first)
        bus.add_middleware(second)
        await bus.publish(OrderCreated(order_id="o1"))
        assert log == [
            "first-before",
            "second-before",
            "handler",
            "second-after",
            "first-after",
        ]

    @pytest.mark.asyncio
    async def test_handler_error_propagates_by_default(self) -> None:
        bus = InMemoryEventBus()

        async def broken(event: DomainEvent) -> None:
            raise ValueError("broken")

        bus.subscribe(OrderCreated, broken)
        with pytest.raises(ValueError, match="broken"):
            await bus.publish(OrderCreated(order_id="o1"))

    @pytest.mark.asyncio
    async def test_on_handler_error_isolates_failures(self) -> None:
        reported: list[Exception] = []
        log: list[str] = []

        def on_error(event: Any, handler: Any, exc: Exception) -> None:
            reported.append(exc)

        bus = InMemoryEventBus(on_handler_error=on_error)

        async def broken(event: DomainEvent) -> None:
            raise ValueError("broken")

        bus.subscribe(OrderCreated, broken)
        bus.subscribe(OrderCreated, Handler(log, "after"))
        await bus.publish(OrderCreated(order_id="o1"))
        # The broken handler is reported; the next handler still runs.
        assert len(reported) == 1
        assert isinstance(reported[0], ValueError)
        assert log == ["after"]

    @pytest.mark.asyncio
    async def test_dead_letter_handler_for_unsubscribed_events(self) -> None:
        dead: list[Any] = []
        bus = InMemoryEventBus(dead_letter_handler=dead.append)
        event = PaymentReceived(amount=5)
        await bus.publish(event)
        assert dead == [event]

    @pytest.mark.asyncio
    async def test_dead_letter_handler_async_supported(self) -> None:
        dead: list[Any] = []

        async def async_dead(event: DomainEvent) -> None:
            dead.append(event)

        bus = InMemoryEventBus(dead_letter_handler=async_dead)
        event = PaymentReceived(amount=5)
        await bus.publish(event)
        assert dead == [event]

    @pytest.mark.asyncio
    async def test_dead_letter_not_called_when_subscribers_exist(self) -> None:
        dead: list[Any] = []
        bus = InMemoryEventBus(dead_letter_handler=dead.append)
        bus.subscribe(OrderCreated, Handler([], "h1"))
        await bus.publish(OrderCreated(order_id="o1"))
        assert dead == []

    @pytest.mark.asyncio
    async def test_handler_timeout_enforced(self) -> None:
        async def slow(event: DomainEvent) -> None:
            await asyncio.sleep(1)

        reported: list[Exception] = []

        def on_error(event: Any, handler: Any, exc: Exception) -> None:
            reported.append(exc)

        bus = InMemoryEventBus(on_handler_error=on_error, handler_timeout=0.01)
        bus.subscribe(OrderCreated, slow)
        await bus.publish(OrderCreated(order_id="o1"))
        assert len(reported) == 1
        assert isinstance(reported[0], (asyncio.TimeoutError, TimeoutError))

    @pytest.mark.asyncio
    async def test_scope_factory_wraps_each_handler(self) -> None:
        entered: list[bool] = []

        class _Scope:
            async def __aenter__(self) -> None:
                entered.append(True)

            async def __aexit__(self, *exc: object) -> None:
                return None

        # The class itself is the factory: each handler gets a fresh scope.
        bus = InMemoryEventBus(scope_factory=_Scope)
        log: list[str] = []
        bus.subscribe(OrderCreated, Handler(log, "h1"))
        await bus.publish(OrderCreated(order_id="o1"))
        assert log == ["h1"]
        assert entered == [True]

    @pytest.mark.asyncio
    async def test_publish_many_is_sequential(self) -> None:
        bus = InMemoryEventBus()
        log: list[str] = []
        bus.subscribe("*", Handler(log, "h1"))
        await bus.publish_many(
            [
                OrderCreated(order_id="1"),
                PaymentReceived(amount=2),
                OrderCreated(order_id="3"),
            ]
        )
        assert log == ["h1", "h1", "h1"]

    @pytest.mark.asyncio
    async def test_subscriber_count_and_subscribed_types(self) -> None:
        bus = InMemoryEventBus()
        h1 = Handler([], "a")
        h2 = Handler([], "b")
        bus.subscribe(OrderCreated, h1)
        bus.subscribe(OrderCreated, h2)
        bus.subscribe("*", Handler([], "wild"))
        assert bus.subscriber_count == 3
        assert bus.subscribed_types == {OrderCreated}
