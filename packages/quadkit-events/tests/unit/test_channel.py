"""Unit tests for _EventChannel.

Covers P1-2: __anext__ must not block forever when the channel closes
while a queue.get() is in-flight.
"""

from __future__ import annotations

import asyncio

import pytest

from quadkit.events.buses._channel import _EventChannel


@pytest.mark.asyncio
async def test_channel_terminates_when_closed_during_wait() -> None:
    """P1-2: __anext__ must not block forever when channel closes during fallback get()."""
    channel: _EventChannel[str] = _EventChannel(capacity=10)

    async def close_after_delay() -> None:
        await asyncio.sleep(0.1)
        await channel.close()  # Close without adding items

    task = asyncio.create_task(close_after_delay())

    items: list[str] = []
    try:
        async with asyncio.timeout(1.0):  # Must NOT hang > 1 second
            async for item in channel:
                items.append(item)
    except TimeoutError:
        pytest.fail("__anext__ blocked indefinitely — P1-2 not fixed")
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    assert items == []
