"""Tests for control and combine operators."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import pytest

from quadkit.reactive import EventStream, Stream, ops


async def gen() -> Any:
    for i in range(10):
        yield i


async def collect(stream: EventStream[Any]) -> list[Any]:
    return [item async for item in stream]


async def test_take_limits_items() -> None:
    assert await collect(Stream(gen()).pipe(ops.take(3))) == [0, 1, 2]


async def test_take_closes_generator_source_on_early_exit() -> None:
    closed = False

    async def source_gen() -> AsyncIterator[int]:
        nonlocal closed
        try:
            for i in range(10):
                yield i
        finally:
            closed = True

    out = await collect(Stream(source_gen()).pipe(ops.take(2)))

    assert out == [0, 1]
    assert closed  # take() broke internally; source was aclosed deterministically


async def test_skip_drops_first_items() -> None:
    assert await collect(Stream(gen()).pipe(ops.skip(7))) == [7, 8, 9]


async def test_merge_interleaves_sources() -> None:
    async def slow() -> Any:
        for x in [1, 2]:
            await asyncio.sleep(0.01)
            yield x

    async def fast() -> Any:
        for x in [10, 20, 30]:
            yield x

    result = await collect(Stream(slow()).pipe(ops.merge(Stream(fast()))))
    assert sorted(result) == [1, 2, 10, 20, 30]


async def test_catch_switches_to_fallback_on_error() -> None:
    async def exploding() -> Any:
        yield 1
        raise RuntimeError("boom")

    async def fallback() -> Any:
        yield 99

    result = await collect(
        Stream(exploding()).pipe(ops.catch(lambda _e: Stream(fallback())))
    )
    assert result == [1, 99]


async def test_catch_emits_default_and_stops() -> None:
    async def exploding() -> Any:
        yield 1
        raise RuntimeError("boom")

    result = await collect(Stream(exploding()).pipe(ops.catch(default=-1)))
    assert result == [1, -1]


async def test_merge_delivers_none_payloads_intact() -> None:
    async def gen_with_none() -> AsyncIterator[int | None]:
        yield None
        yield 7

    async def gen_plain() -> AsyncIterator[int]:
        yield 1

    result = await collect(Stream(gen_with_none()).pipe(ops.merge(Stream(gen_plain()))))
    assert result == [None, 7, 1]


async def test_merge_propagates_feed_error_and_cancels_other_feeds() -> None:
    finished = False

    async def bad() -> AsyncIterator[int]:
        yield 1
        raise RuntimeError("boom")

    async def slow_good() -> AsyncIterator[int]:
        nonlocal finished
        try:
            for i in range(100):
                yield i
                await asyncio.sleep(0.01)
        finally:
            finished = True

    collected: list[Any] = []

    async def drain() -> None:
        async for item in Stream(bad()).pipe(ops.merge(Stream(slow_good()))):
            collected.append(item)

    with pytest.raises(RuntimeError, match="boom"):
        await drain()

    assert 1 in collected
    await asyncio.sleep(0.05)
    assert finished  # losing feed was cancelled, not left running


async def test_on_end_complete_callback_fires_once_sync_and_async() -> None:
    calls: list[str] = []

    async def acomplete() -> None:
        calls.append("a")

    def scomplete() -> None:
        calls.append("s")

    first = await collect(Stream(gen()).pipe(ops.on_end(on_complete=scomplete)))
    assert first == list(range(10))

    second = await collect(Stream(gen()).pipe(ops.on_end(on_complete=acomplete)))
    assert second == list(range(10))

    assert calls == ["s", "a"]


async def test_on_end_error_callback_fires_then_reraises() -> None:
    seen: list[BaseException] = []

    def on_error(exc: BaseException) -> None:
        seen.append(exc)

    async def failing() -> AsyncIterator[int]:
        yield 1
        raise ValueError("late")

    collected: list[Any] = []

    async def drain() -> None:
        async for item in Stream(failing()).pipe(ops.on_end(on_error=on_error)):
            collected.append(item)

    with pytest.raises(ValueError, match="late"):
        await drain()

    assert collected == [1]
    assert len(seen) == 1 and isinstance(seen[0], ValueError)


async def test_on_end_without_callbacks_is_passthrough() -> None:
    assert await collect(Stream(gen()).pipe(ops.on_end())) == list(range(10))
