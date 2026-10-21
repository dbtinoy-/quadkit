"""``close()`` must end a consumer that is waiting on an empty channel.

Found through ``quadkit-events``: the event bus drains each channel with
``async for``, and nothing could stop those drain tasks at shutdown because
a receiver blocked in ``queue.get()`` never learned the channel had closed.
"""

from __future__ import annotations

import asyncio

import pytest

from quadkit.concurrency import BoundedChannel
from quadkit.concurrency.exceptions import ChannelClosedError


async def test_close_wakes_a_receiver_blocked_on_an_empty_channel() -> None:
    channel: BoundedChannel[int] = BoundedChannel(capacity=4)
    waiting = asyncio.create_task(channel.receive())
    await asyncio.sleep(0)
    assert not waiting.done()

    await channel.close()

    with pytest.raises(ChannelClosedError):
        await asyncio.wait_for(waiting, timeout=1)


async def test_async_for_ends_after_close_and_still_yields_queued_items() -> None:
    channel: BoundedChannel[int] = BoundedChannel(capacity=4)
    seen: list[int] = []

    async def consume() -> None:
        async for item in channel:
            seen.append(item)

    consumer = asyncio.create_task(consume())
    await channel.send(1)
    await channel.send(2)
    await asyncio.sleep(0)
    await channel.close()

    await asyncio.wait_for(consumer, timeout=1)
    assert seen == [1, 2]


async def test_an_item_sent_just_before_close_is_delivered() -> None:
    channel: BoundedChannel[int] = BoundedChannel(capacity=4)
    waiting = asyncio.create_task(channel.receive())
    await asyncio.sleep(0)

    await channel.send(7)
    await channel.close()

    assert await asyncio.wait_for(waiting, timeout=1) == 7
    with pytest.raises(ChannelClosedError):
        await channel.receive()


async def test_cancelling_a_waiting_receiver_loses_nothing() -> None:
    channel: BoundedChannel[int] = BoundedChannel(capacity=4)
    waiting = asyncio.create_task(channel.receive())
    await asyncio.sleep(0)
    waiting.cancel()
    with pytest.raises(asyncio.CancelledError):
        await waiting

    await channel.send(3)
    assert await channel.receive() == 3
    assert channel.is_empty


async def test_two_receivers_both_end_on_close() -> None:
    channel: BoundedChannel[int] = BoundedChannel(capacity=4)
    first = asyncio.create_task(channel.receive())
    second = asyncio.create_task(channel.receive())
    await asyncio.sleep(0)

    await channel.close()
    results = await asyncio.gather(first, second, return_exceptions=True)
    assert all(isinstance(result, ChannelClosedError) for result in results)


async def test_an_item_is_queued_or_received_never_in_between() -> None:
    """``is_empty`` must not turn true before the consumer holds the item.

    The event bus's ``flush()`` polls ``is_empty`` and an in-flight counter
    the consumer bumps right after ``receive()`` returns. If the receiver
    dequeued inside a helper task there would be one loop tick where the
    queue is empty and nothing is in flight — and ``flush()`` would return
    before the handler ran. Caught by a stock→channel test that asserted a
    push the debouncer had not yet been handed.
    """
    channel: BoundedChannel[int] = BoundedChannel(capacity=4)
    held: list[int] = []

    async def consume() -> None:
        async for item in channel:
            held.append(item)

    consumer = asyncio.create_task(consume())
    await asyncio.sleep(0)  # consumer is now parked on the empty channel

    for n in range(3):
        await channel.send(n)
        # From the sender's point of view, every tick until the consumer
        # resumes must still show the item as queued.
        while not held or held[-1] != n:
            assert not channel.is_empty, "item vanished before the consumer resumed"
            await asyncio.sleep(0)

    await channel.close()
    await asyncio.wait_for(consumer, timeout=1)
    assert held == [0, 1, 2]
