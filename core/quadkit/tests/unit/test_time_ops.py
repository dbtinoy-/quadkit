"""Tests for time-based operators: debounce, throttle, buffer, window."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from quadkit.reactive.core import Stream
from quadkit.reactive.operators.time_ops import buffer, debounce, throttle, window


class FakeClock:
    """Manually advanced clock for deterministic timing tests."""

    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


async def _collect(stream: Stream, limit: int = 1000) -> list[Any]:
    out: list[Any] = []
    i = 0
    async for item in stream:
        out.append(item)
        i += 1
        if i >= limit:
            break
    return out


def _items(*values: Any) -> AsyncIterator[Any]:
    async def gen() -> AsyncIterator[Any]:
        for v in values:
            yield v

    return gen()


class TestDebounce:
    async def test_burst_collapses_to_final(self) -> None:
        clock = FakeClock()
        result_stream = debounce(1.0, clock)(_items(1, 2, 3))
        task = __import__("asyncio").create_task(_collect(result_stream, limit=1))
        # Let the feed task enqueue all items, then advance past the quiet period.
        await __import__("asyncio").sleep(0.01)
        clock.advance(1.1)
        got = await __import__("asyncio").wait_for(task, timeout=5.0)
        assert got == [3]

    async def test_quiet_gap_emits_then_final(self) -> None:
        clock = FakeClock()

        async def gen() -> AsyncIterator[Any]:
            yield 1
            yield 2

        # Items arrive back-to-back with no real delay; advance the clock
        # past the quiet period so the debounce flushes at end-of-stream.
        result_stream = debounce(1.0, clock)(Stream(gen()))
        out = await _collect(result_stream, limit=5)
        assert out == [2]

    async def test_intermediate_emission_after_silence(self) -> None:
        import asyncio

        clock = FakeClock()
        emitted: list[Any] = []
        release_second = asyncio.Event()

        async def gen() -> AsyncIterator[Any]:
            yield 1
            await release_second.wait()  # hold the second item
            yield 2

        stream = debounce(1.0, clock)(Stream(gen()))

        async def consume() -> None:
            async for item in stream:
                emitted.append(item)

        task = asyncio.create_task(consume())
        await asyncio.sleep(0.02)  # let the feed task enqueue item 1
        clock.advance(2.0)  # silence in fake time
        await asyncio.sleep(1.05)  # real wait_for(1.0s) fires → emit stale item
        assert emitted == [1]
        release_second.set()  # item 2 + end of stream arrive back-to-back
        await task  # sentinel flush emits 2
        assert emitted == [1, 2]


class TestThrottle:
    async def test_first_item_passes_then_interval_enforced(self) -> None:
        clock = FakeClock()
        out: list[Any] = []

        async def gen() -> AsyncIterator[Any]:
            yield "a"
            clock.advance(0.4)
            yield "b"  # too soon → dropped
            clock.advance(0.7)  # t=1.1 ≥ next_allowed(1.0)
            yield "c"
            clock.advance(0.1)
            yield "d"  # t=1.2 < next_allowed(2.0) → dropped

        stream = throttle(1.0, clock)(Stream(gen()))
        async for item in stream:
            out.append(item)
        assert out == ["a", "c"]

    async def test_zero_interval_passes_all(self) -> None:
        clock = FakeClock()
        stream = throttle(0.0, clock)(_items(1, 2, 3))
        assert await _collect(stream) == [1, 2, 3]


class TestBuffer:
    async def test_full_batches_and_remainder(self) -> None:
        stream = buffer(2)(_items(1, 2, 3, 4, 5))
        assert await _collect(stream) == [[1, 2], [3, 4], [5]]

    async def test_exact_multiple_no_trailing_empty(self) -> None:
        stream = buffer(2)(_items(1, 2, 3, 4))
        assert await _collect(stream) == [[1, 2], [3, 4]]

    async def test_single_item(self) -> None:
        stream = buffer(3)(_items(42))
        assert await _collect(stream) == [[42]]

    async def test_empty_stream(self) -> None:
        stream = buffer(2)(_items())
        assert await _collect(stream) == []


class TestWindow:
    async def test_batches_by_window_and_flush(self) -> None:
        clock = FakeClock()

        async def gen() -> AsyncIterator[Any]:
            yield 1
            clock.advance(1.0)  # crosses window boundary on next item
            yield 2
            yield 3  # same window as 2
            clock.advance(1.0)  # crosses again
            yield 4

        stream = window(1.0, clock)(Stream(gen()))
        assert await _collect(stream) == [[1], [2, 3], [4]]

    async def test_all_in_one_window(self) -> None:
        clock = FakeClock()
        stream = window(10.0, clock)(_items(1, 2, 3))
        assert await _collect(stream) == [[1, 2, 3]]

    async def test_empty_stream(self) -> None:
        clock = FakeClock()
        stream = window(1.0, clock)(_items())
        assert await _collect(stream) == []


class TestResolveClock:
    def test_defaults_to_ambient_clock(self) -> None:
        from quadkit.primitives import clock as ambient
        from quadkit.reactive.operators.time_ops import _resolve_clock

        resolved = _resolve_clock(None)
        assert resolved is ambient.monotonic

    def test_explicit_clock_used(self) -> None:
        from quadkit.reactive.operators.time_ops import _resolve_clock

        c = FakeClock()
        assert _resolve_clock(c) is c
