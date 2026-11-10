"""Subscriber failure must not advance a checkpoint past unhandled events."""

from __future__ import annotations

import asyncio

import pytest

from quadkit.events.messages.event import Event
from quadkit.events.stores.checkpoints import InMemoryCheckpointStore
from quadkit.events.stores.memory import InMemoryEventStore
from quadkit.events.stores.sqlite.event_store import SqliteEventStore
from quadkit.events.streaming.subscriber import EventSubscriber, SubscriptionState
from quadkit.sql.providers.sqlite_provider import SQLiteProvider


class Message(Event):
    pass


async def wait_until(predicate, timeout=4):
    async def wait():
        while not predicate():
            await asyncio.sleep(0.01)

    await asyncio.wait_for(wait(), timeout)


@pytest.mark.asyncio
@pytest.mark.parametrize("backend", ["memory", "sqlite"])
async def test_failed_handler_is_retried_before_later_events_and_checkpoint(
    tmp_path, backend
):
    provider = None
    if backend == "sqlite":
        provider = SQLiteProvider(str(tmp_path / "events.sqlite"))
        await provider.connect()
        store = SqliteEventStore(provider=provider)
        await store.connect()
        store.register_event_type("Message", Message)
    else:
        store = InMemoryEventStore()
    checkpoints = InMemoryCheckpointStore()
    attempts = []
    delivered = []
    allow_retry = False

    async def handler(event):
        attempts.append(event.label)
        if event.label == "bad" and not allow_retry:
            raise RuntimeError("transient failure")
        delivered.append(event.label)

    subscriber = EventSubscriber(
        event_store=store,
        checkpoint_store=checkpoints,
        checkpoint_interval=1,
        total_partitions=1,
    )
    try:
        await store.append(
            "s", [Message(label="first"), Message(label="bad"), Message(label="later")]
        )
        sub = await subscriber.subscribe("items", handler, group_id="g", partition=0)
        await subscriber.start()
        await wait_until(lambda: sub.errors >= 1)
        assert attempts == ["first", "bad"]
        assert delivered == ["first"]
        assert sub.position == 1
        assert await checkpoints.get_checkpoint("sub:g:items:0") == 1
        allow_retry = True
        await wait_until(lambda: len(delivered) == 3)
        assert attempts == ["first", "bad", "bad", "later"]
        assert delivered == ["first", "bad", "later"]
        assert sub.position == 3
        assert await checkpoints.get_checkpoint("sub:g:items:0") == 3
    finally:
        await subscriber.stop()
        await asyncio.sleep(0)
        if provider is not None:
            await provider.disconnect()


@pytest.mark.asyncio
async def test_future_handler_failure_does_not_checkpoint_past_event():
    store = InMemoryEventStore()
    checkpoints = InMemoryCheckpointStore()
    seen = []

    def handler(event):
        seen.append(event.label)
        future = asyncio.get_running_loop().create_future()
        if event.label == "bad":
            future.set_exception(RuntimeError("failure"))
        else:
            future.set_result(None)
        return future

    subber = EventSubscriber(
        event_store=store,
        checkpoint_store=checkpoints,
        checkpoint_interval=1,
        total_partitions=1,
    )
    await store.append("s", [Message(label="bad"), Message(label="later")])
    sub = await subber.subscribe("futures", handler, group_id="g", partition=0)
    try:
        await subber.start()
        await wait_until(lambda: sub.errors >= 1 or "later" in seen)
        assert seen == ["bad"]
        assert sub.errors == 1
        assert sub.position == 0
        assert await checkpoints.get_checkpoint("sub:g:futures:0") == 0
    finally:
        await subber.stop()
        await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_missing_stream_cursor_fails_before_dispatch():
    class BrokenStore:
        async def stream_all(self, **kwargs):
            yield Message(label="missing-position")

    seen = []
    subscriber = EventSubscriber(event_store=BrokenStore())
    sub = await subscriber.subscribe("missing", lambda event: seen.append(event.label))
    try:
        await subscriber.start()
        await wait_until(lambda: sub.state == SubscriptionState.ERROR)
        assert not seen
        assert sub.position == 0
    finally:
        await subscriber.stop()
        await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_checkpoint_failure_stops_consumer_without_advancing_to_next_event():
    class BrokenCheckpoint(InMemoryCheckpointStore):
        async def save_checkpoint(self, name, position):
            raise RuntimeError("unavailable")

    store = InMemoryEventStore()
    await store.append("s", [Message(label="first"), Message(label="later")])
    seen = []
    subscriber = EventSubscriber(
        event_store=store,
        checkpoint_store=BrokenCheckpoint(),
        checkpoint_interval=1,
        total_partitions=1,
    )
    sub = await subscriber.subscribe(
        "failure", lambda event: seen.append(event.label), group_id="g", partition=0
    )
    try:
        await subscriber.start()
        await wait_until(
            lambda: sub.state == SubscriptionState.ERROR or "later" in seen
        )
        assert sub.state == SubscriptionState.ERROR
        assert seen == ["first"]
    finally:
        await subscriber.stop()
        await asyncio.sleep(0)


@pytest.mark.parametrize("interval", [0, -1, True])
def test_invalid_checkpoint_interval(interval):
    with pytest.raises(ValueError, match="checkpoint_interval"):
        EventSubscriber(checkpoint_interval=interval)


@pytest.mark.asyncio
async def test_failed_event_replayed_after_sqlite_reopen_and_consumer_restart(tmp_path):
    path = str(tmp_path / "restart.sqlite")
    checkpoint = InMemoryCheckpointStore()
    first_provider = SQLiteProvider(path)
    await first_provider.connect()
    store = SqliteEventStore(provider=first_provider)
    await store.connect()
    store.register_event_type("Message", Message)
    await store.append(
        "s", [Message(label="first"), Message(label="bad"), Message(label="later")]
    )
    first_subscriber = EventSubscriber(
        event_store=store,
        checkpoint_store=checkpoint,
        checkpoint_interval=1,
        total_partitions=1,
    )
    first_seen = []

    async def failing(event):
        first_seen.append(event.label)
        if event.label == "bad":
            raise RuntimeError("failed")

    first = await first_subscriber.subscribe(
        "items", failing, group_id="g", partition=0
    )
    try:
        await first_subscriber.start()
        await wait_until(lambda: first.errors == 1)
        assert first_seen == ["first", "bad"]
        assert await checkpoint.get_checkpoint("sub:g:items:0") == 1
    finally:
        await first_subscriber.stop()
        await asyncio.sleep(0)
        await first_provider.disconnect()

    second_provider = SQLiteProvider(path)
    await second_provider.connect()
    reopened = SqliteEventStore(provider=second_provider)
    await reopened.connect()
    reopened.register_event_type("Message", Message)
    second_subscriber = EventSubscriber(
        event_store=reopened,
        checkpoint_store=checkpoint,
        checkpoint_interval=1,
        total_partitions=1,
    )
    second_seen = []
    second = await second_subscriber.subscribe(
        "items",
        lambda event: second_seen.append(event.label),
        group_id="g",
        partition=0,
    )
    try:
        assert second.position == 1
        await second_subscriber.start()
        await wait_until(lambda: len(second_seen) == 2)
        assert second_seen == ["bad", "later"]
        assert second.position == 3
        assert await checkpoint.get_checkpoint("sub:g:items:0") == 3
    finally:
        await second_subscriber.stop()
        await asyncio.sleep(0)
        await second_provider.disconnect()


@pytest.mark.asyncio
async def test_out_of_order_positions_fail_even_when_previous_event_is_filtered():
    class BrokenStore:
        async def stream_all(self, **kwargs):
            yield Event(sequence_number=5)
            yield Message(label="out-of-order", sequence_number=4)

    seen = []
    subscriber = EventSubscriber(event_store=BrokenStore())
    sub = await subscriber.subscribe(
        "out-of-order", lambda event: seen.append(event.label), event_types={Message}
    )
    try:
        await subscriber.start()
        await wait_until(lambda: sub.state == SubscriptionState.ERROR)
        assert not seen
        assert sub.position == 0
    finally:
        await subscriber.stop()
        await asyncio.sleep(0)


@pytest.mark.parametrize("change", ["pause", "stop_subscription", "stop_subscriber"])
async def test_state_changed_during_stream_await_blocks_delivery_and_checkpoint(change):
    requested = asyncio.Event()
    release = asyncio.Event()

    class SuspendingStore:
        async def stream_all(self, **kwargs):
            requested.set()
            await release.wait()
            yield Message(label="must-not-deliver", sequence_number=1)

    class TrackingCheckpointStore(InMemoryCheckpointStore):
        def __init__(self):
            super().__init__()
            self.writes = []

        async def save_checkpoint(self, name, position):
            self.writes.append((name, position))
            await super().save_checkpoint(name, position)

    checkpoints = TrackingCheckpointStore()
    delivered = []

    async def handler(event):
        delivered.append(event)

    subscriber = EventSubscriber(
        event_store=SuspendingStore(),
        checkpoint_store=checkpoints,
        checkpoint_interval=1,
    )
    sub = await subscriber.subscribe("paused_stream", handler)
    # Drive the consumer directly to exercise the live-state guard, not the
    # public pause/stop APIs' cancellation of a registered background task.
    subscriber._running = True
    task = asyncio.create_task(subscriber._consume(sub))
    try:
        await asyncio.wait_for(requested.wait(), 2)
        if change == "pause":
            sub.state = SubscriptionState.PAUSED
        elif change == "stop_subscription":
            sub.state = SubscriptionState.STOPPED
        else:
            await subscriber.stop()
        release.set()
        await asyncio.wait_for(task, 2)
        assert delivered == []
        assert sub.position == 0
        assert sub.events_processed == 0
        assert await checkpoints.get_checkpoint("paused_stream") == 0
        assert checkpoints.writes == []
    finally:
        release.set()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await subscriber.stop()
