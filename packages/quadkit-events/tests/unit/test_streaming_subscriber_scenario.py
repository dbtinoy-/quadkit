"""Scenario tests for the streaming event subscriber.

Drives ``EventSubscriber`` against the real ``InMemoryEventStore`` +
``InMemoryCheckpointStore``: live consumption with position tracking,
event-type filtering, group/checkpoint position restore, per-message error
isolation, and pause/resume.  Polling uses deadline-based waits (never
fixed sleeps) so the suite stays fast and deterministic.
"""

from __future__ import annotations

import asyncio
from typing import Any

from quadkit.events.messages.event import Event
from quadkit.events.stores.checkpoints import InMemoryCheckpointStore
from quadkit.events.stores.memory import InMemoryEventStore
from quadkit.events.streaming.subscriber import (
    EventSubscriber,
    SubscriptionState,
)


class OrderCreated(Event):
    order_id: str = "o1"


class OrderShipped(Event):
    order_id: str = "o1"


async def _wait_until(predicate: Any, timeout: float = 10.0, step: float = 0.05) -> bool:
    """Poll *predicate* until truthy or the deadline passes."""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        if predicate():
            return True
        await asyncio.sleep(step)
    return predicate()


async def test_subscriber_consumes_filters_and_checkpoints() -> None:
    """Live consumption with type filtering, positions, and checkpoints."""
    store = InMemoryEventStore()
    checkpoint_store = InMemoryCheckpointStore()
    subscriber = EventSubscriber(
        event_store=store,
        checkpoint_store=checkpoint_store,
        checkpoint_interval=2,
    )

    received: list[str] = []

    async def handler(event: Event) -> None:
        received.append(event.order_id)  # type: ignore[attr-defined]

    subscription = await subscriber.subscribe(
        "orders",
        handler,
        event_types={OrderCreated},
        group_id="g1",
        partition=1,
    )
    assert subscription.state is SubscriptionState.ACTIVE

    await subscriber.start()
    await store.append("orders", [OrderCreated(order_id="o1")])
    await store.append("orders", [OrderShipped(order_id="o1")])
    await store.append("orders", [OrderCreated(order_id="o2")])

    assert await _wait_until(lambda: len(received) == 2)
    assert received == ["o1", "o2"]  # shipped events filtered out
    assert subscription.events_processed == 2
    assert subscription.position == 3

    # checkpoints persisted under the group/partition key
    checkpoint = await checkpoint_store.get_checkpoint("sub:g1:orders:1")
    assert checkpoint == 3

    await subscriber.stop()


async def test_subscriber_restores_position_from_checkpoint() -> None:
    """A group subscription resumes where its checkpoint left off."""
    store = InMemoryEventStore()
    checkpoint_store = InMemoryCheckpointStore()
    for i in range(1, 6):
        await store.append("orders", [OrderCreated(order_id=f"o{i}")])

    # a previous consumer left the checkpoint at position 2
    await checkpoint_store.save_checkpoint("sub:g1:late:1", 2)

    subscriber = EventSubscriber(
        event_store=store,
        checkpoint_store=checkpoint_store,
    )
    received: list[str] = []

    async def handler(event: Event) -> None:
        received.append(event.order_id)  # type: ignore[attr-defined]

    subscription = await subscriber.subscribe(
        "late",
        handler,
        from_position=0,
        group_id="g1",
        partition=1,
    )
    assert subscription.position == 2  # restored, not the requested 0

    await subscriber.start()
    assert await _wait_until(lambda: len(received) == 3)
    assert received == ["o3", "o4", "o5"]  # only events after the checkpoint
    await subscriber.stop()


async def test_subscriber_error_isolation_and_pause() -> None:
    """A failing message is counted, not fatal; pause stops consumption."""
    store = InMemoryEventStore()
    subscriber = EventSubscriber(event_store=store)

    received: list[str] = []
    errors: list[str] = []

    async def handler(event: Event) -> None:
        order_id = event.order_id  # type: ignore[attr-defined]
        if order_id == "bad":
            errors.append(order_id)
            msg = "poison message"
            raise RuntimeError(msg)
        received.append(order_id)

    subscription = await subscriber.subscribe("mixed", handler)
    await subscriber.start()

    await store.append("m", [OrderCreated(order_id="ok1")])
    await store.append("m", [OrderCreated(order_id="bad")])
    assert await _wait_until(lambda: subscription.errors == 1)
    assert subscription.errors == 1
    assert errors == ["bad"]
    assert subscription.state is SubscriptionState.ACTIVE  # still alive

    # pause: nothing new is consumed while paused
    assert await subscriber.pause(subscription.id) is True
    assert subscription.state is SubscriptionState.PAUSED
    await store.append("m", [OrderCreated(order_id="while-paused")])
    await asyncio.sleep(0.3)
    assert "while-paused" not in received

    # resume: consumption continues from the saved position
    assert await subscriber.resume(subscription.id) is True
    assert await _wait_until(lambda: "while-paused" in received)
    assert subscription.position == 3

    await subscriber.stop()
    assert await subscriber.unsubscribe(subscription.id) is True
    assert await subscriber.unsubscribe(subscription.id) is False
