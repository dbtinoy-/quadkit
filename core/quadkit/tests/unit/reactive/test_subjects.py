"""Tests for hot subjects and sharing."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import pytest

from quadkit.reactive import EventStream, Stream, Subject, share


async def collect_until(stream: EventStream[Any], count: int) -> list[Any]:
    items: list[Any] = []
    async for item in stream:
        items.append(item)
        if len(items) >= count:
            break
    return items


async def test_subject_fans_out_to_subscribers() -> None:
    subject = Subject[int]()
    received_a: list[int] = []
    received_b: list[int] = []

    async def consume_a() -> None:
        async for item in subject:
            received_a.append(item)

    async def consume_b() -> None:
        async for item in subject:
            received_b.append(item)

    task_a = asyncio.create_task(consume_a())
    task_b = asyncio.create_task(consume_b())
    await asyncio.sleep(0.01)
    for i in range(3):
        await subject.publish(i)
    await asyncio.sleep(0.01)
    await subject.complete()
    await asyncio.gather(task_a, task_b)
    assert received_a == [0, 1, 2]
    assert received_b == [0, 1, 2]


async def test_share_runs_source_into_subject() -> None:
    async def gen() -> Any:
        for i in range(3):
            yield i
            await asyncio.sleep(0.01)

    subject = share(Stream(gen()))
    items = await collect_until(subject, 3)
    assert items == [0, 1, 2]
    await subject.complete()


async def test_share_is_hot_between_publishes() -> None:
    async def gen() -> Any:
        yield "first"
        await asyncio.sleep(0.05)
        yield "second"

    subject = share(Stream(gen()))
    await asyncio.sleep(0.02)  # "first" already published
    got = await collect_until(subject, 1)
    assert got == ["second"]


async def test_subject_error_terminates_subscribers_with_exception() -> None:
    subject: Subject[int] = Subject()
    received: list[int] = []

    async def consume() -> None:
        try:
            async for item in subject:
                received.append(item)
        except ValueError as exc:
            received.append(-1)  # marker
            assert str(exc) == "bad"

    task = asyncio.create_task(consume())
    await asyncio.sleep(0.01)

    await subject.publish(1)
    await subject.publish(2)
    await subject.error(ValueError("bad"))
    await asyncio.wait_for(task, timeout=2)

    assert received == [1, 2, -1]
    # publish after error is a no-op, not an explosion
    await subject.publish(3)
    assert received == [1, 2, -1]


async def test_share_propagates_pump_errors_to_subscribers() -> None:
    async def failing_source() -> AsyncIterator[int]:
        yield 1
        raise RuntimeError("pump died")

    subject = share(Stream(failing_source()))

    received: list[int] = []

    async def drain() -> None:
        async for item in subject:
            received.append(item)

    with pytest.raises(RuntimeError, match="pump died"):
        await drain()

    assert received == [1]

async def test_drop_oldest_keeps_newest_items_for_slow_subscriber() -> None:
    subject = Subject[int](channel_capacity=3, on_overflow="drop_oldest")
    subscription = subject.subscribe()
    for i in range(6):
        await subject.publish(i)

    received: list[int] = []
    async for item in subscription:
        received.append(item)
        if len(received) == 3:
            break
    await subscription.aclose()

    assert received == [3, 4, 5]
    assert subject.subscriber_count == 0


async def test_drop_latest_discards_incoming_item_for_full_subscriber() -> None:
    subject = Subject[int](channel_capacity=3, on_overflow="drop_latest")
    subscription = subject.subscribe()
    for i in range(6):
        await subject.publish(i)

    received: list[int] = []
    async for item in subscription:
        received.append(item)
        if len(received) == 3:
            break
    await subscription.aclose()

    assert received == [0, 1, 2]


def test_unknown_overflow_mode_is_rejected() -> None:
    with pytest.raises(ValueError, match="on_overflow"):
        Subject[int](on_overflow="explode")


async def test_late_subscriber_receives_replay_then_live_items() -> None:
    subject = Subject[str](replay=2)
    for item in ("a", "b", "c"):
        await subject.publish(item)

    received: list[str] = []

    async def consume() -> None:
        async for item in subject:
            received.append(item)

    task = asyncio.create_task(consume())
    await asyncio.sleep(0.01)
    await subject.publish("d")
    await asyncio.sleep(0.01)
    await subject.complete()
    await task

    assert received == ["b", "c", "d"]


async def test_replay_seed_is_capped_at_channel_capacity() -> None:
    subject = Subject[int](channel_capacity=2, replay=5, on_overflow="drop_oldest")
    for i in range(5):
        await subject.publish(i)

    subscription = subject.subscribe()
    received: list[int] = []
    async for item in subscription:
        received.append(item)
        if len(received) == 2:
            break
    await subscription.aclose()

    assert received == [3, 4]


async def test_replay_snapshot_is_oldest_first_and_bounded() -> None:
    subject = Subject[int](replay=3)
    for i in range(5):
        await subject.publish(i)

    assert subject.replay_snapshot() == [2, 3, 4]
    assert Subject[int]().replay_snapshot() == []


async def test_publish_during_registration_window_is_delivered_exactly_once() -> None:
    subject = Subject[str](replay=10)
    await subject.publish("seed")

    # subscribe() registers synchronously; an item published after that but
    # before the first __anext__ arrives via the channel, never twice via
    # the replay seed.
    subscription = subject.subscribe()
    await subject.publish("late")

    received: list[str] = []
    async for item in subscription:
        received.append(item)
        if len(received) == 2:
            break
    await subscription.aclose()

    assert received == ["seed", "late"]


async def test_completed_subject_replays_history_then_ends() -> None:
    subject = Subject[int](replay=2)
    await subject.publish(1)
    await subject.publish(2)
    await subject.complete()

    received = [item async for item in subject]

    assert received == [1, 2]


async def test_failed_subject_replays_history_then_raises() -> None:
    subject = Subject[int](replay=2)
    await subject.publish(1)
    await subject.error(ValueError("bad"))

    received: list[int] = []
    with pytest.raises(ValueError, match="bad"):
        async for item in subject:
            received.append(item)

    assert received == [1]


async def test_subscriber_count_tracks_attached_subscribers() -> None:
    subject = Subject[int]()
    assert subject.subscriber_count == 0

    first = subject.subscribe()
    second = subject.subscribe()
    assert subject.subscriber_count == 2

    await first.aclose()
    await first.aclose()  # idempotent
    assert subject.subscriber_count == 1

    await subject.publish(7)
    await subject.complete()
    drained = [item async for item in second]

    assert drained == [7]
    assert subject.subscriber_count == 0
