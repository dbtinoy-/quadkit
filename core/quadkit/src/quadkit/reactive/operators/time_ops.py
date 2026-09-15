"""Time-based operators: debounce, throttle, buffer, window."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import suppress
from typing import Any

from quadkit.primitives import clock as ambient_clock
from quadkit.reactive.core import EventStream, Stream


def _resolve_clock(clock: Callable[[], float] | None) -> Callable[[], float]:
    return clock or ambient_clock.monotonic


def debounce(seconds: float, clock: Callable[[], float] | None = None) -> Any:
    """Emit an item only after ``seconds`` of silence.

    Args:
        seconds: Quiet period required before an item is emitted.
        clock: Optional time source; defaults to the ambient clock.

    Returns:
        An operator that collapses bursts into their final item.
    """

    now = _resolve_clock(clock)

    def _op(source: EventStream[Any]) -> EventStream[Any]:
        async def _gen() -> AsyncIterator[Any]:
            queue: asyncio.Queue[Any] = asyncio.Queue()
            sentinel = object()

            async def _feed() -> None:
                async for item in source:
                    await queue.put(item)
                await queue.put(sentinel)

            feed_task = asyncio.create_task(_feed())

            last: Any = None
            last_time: float | None = None
            have_item = False
            while True:
                poll = seconds if have_item else None
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=poll)
                except TimeoutError:
                    if (
                        have_item
                        and last_time is not None
                        and (now() - last_time) >= seconds
                    ):
                        yield last
                        have_item = False
                    continue
                if item is sentinel:
                    if have_item:
                        yield last
                    break
                last = item
                last_time = now()
                have_item = True
            feed_task.cancel()
            with suppress(asyncio.CancelledError):
                await feed_task

        return Stream(_gen())

    return _op


def throttle(interval: float, clock: Callable[[], float] | None = None) -> Any:
    """Emit at most one item per ``interval``.

    Args:
        interval: Minimum time between emissions.
        clock: Optional time source; defaults to the ambient clock.

    Returns:
        An operator that rate-limits the stream.
    """

    now = _resolve_clock(clock)

    def _op(source: EventStream[Any]) -> EventStream[Any]:
        async def _gen() -> AsyncIterator[Any]:
            next_allowed = 0.0
            async for item in source:
                t = now()
                if t >= next_allowed:
                    yield item
                    next_allowed = t + interval

        return Stream(_gen())

    return _op


def buffer(count: int) -> Any:
    """Emit batches of ``count`` items; flush remainder on end.

    Args:
        count: Batch size.

    Returns:
        An operator emitting ``list[T]`` batches.
    """

    def _op(source: EventStream[Any]) -> EventStream[Any]:
        async def _gen() -> AsyncIterator[Any]:
            batch: list[Any] = []
            async for item in source:
                batch.append(item)
                if len(batch) >= count:
                    yield batch
                    batch = []
            if batch:
                yield batch

        return Stream(_gen())

    return _op


def window(seconds: float, clock: Callable[[], float] | None = None) -> Any:
    """Emit batches per ``seconds`` window; flush remainder on end.

    Args:
        seconds: Window length in seconds.
        clock: Optional time source; defaults to the ambient clock.

    Returns:
        An operator emitting ``list[T]`` batches per window.
    """

    now = _resolve_clock(clock)

    def _op(source: EventStream[Any]) -> EventStream[Any]:
        async def _gen() -> AsyncIterator[Any]:
            batch: list[Any] = []
            window_start = now()
            async for item in source:
                if now() - window_start >= seconds:
                    yield batch
                    batch = []
                    window_start = now()
                batch.append(item)
            if batch:
                yield batch

        return Stream(_gen())

    return _op
