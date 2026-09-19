"""Tests for time-based operators with an injectable clock."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from quadkit.reactive import EventStream, Stream, ops


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, delta: float) -> None:
        self.now += delta


async def collect(stream: EventStream[Any]) -> list[Any]:
    return [item async for item in stream]


def manual(source: list[Any], clock: FakeClock, tick: float) -> AsyncIterator[Any]:
    async def _gen() -> Any:
        for item in source:
            yield item
            clock.advance(tick)
            await asyncio.sleep(0)

    return _gen()


async def test_debounce_emits_last_item_of_burst() -> None:
    clock = FakeClock()
    stream = Stream(manual([1, 2, 3], clock, tick=3.0)).pipe(
        ops.debounce(seconds=2.0, clock=clock)
    )
    assert await collect(stream) == [3]


async def test_throttle_emits_one_per_interval() -> None:
    clock = FakeClock()
    stream = Stream(manual([1, 2, 3, 4, 5], clock, tick=0.5)).pipe(
        ops.throttle(interval=1.0, clock=clock)
    )
    assert await collect(stream) == [1, 3, 5]


async def test_buffer_batches_by_count() -> None:
    stream = Stream(manual([1, 2, 3, 4, 5], FakeClock(), tick=0.0)).pipe(
        ops.buffer(count=2)
    )
    assert await collect(stream) == [[1, 2], [3, 4], [5]]


async def test_window_batches_by_time_and_flushes_remainder() -> None:
    clock = FakeClock()
    stream = Stream(manual([1, 2, 3, 4], clock, tick=4.0)).pipe(
        ops.window(seconds=5.0, clock=clock)
    )
    assert await collect(stream) == [[1, 2], [3, 4]]