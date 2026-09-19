"""Control and combination operators: take, skip, merge, catch."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import suppress
import inspect
from typing import Any

from quadkit.reactive.core import EventStream, Stream


def take(count: int) -> Any:
    """Emit at most ``count`` items, then stop and close the source.

    Args:
        count: Maximum number of items to emit. ``0`` emits nothing.

    Returns:
        An operator that truncates the stream.
    """

    def _op(source: EventStream[Any]) -> EventStream[Any]:
        async def _gen() -> AsyncIterator[Any]:
            seen = 0
            try:
                async for item in source:
                    if seen >= count:
                        break
                    yield item
                    seen += 1
            finally:
                if seen >= count:
                    src_iter = source.__aiter__()
                    aclose = getattr(src_iter, "aclose", None)
                    if aclose is not None:
                        await aclose()

        return Stream(_gen())

    return _op


def skip(count: int) -> Any:
    """Drop the first ``count`` items.

    Args:
        count: Number of initial items to drop.

    Returns:
        An operator that discards leading items.
    """

    def _op(source: EventStream[Any]) -> EventStream[Any]:
        async def _gen() -> AsyncIterator[Any]:
            seen = 0
            async for item in source:
                if seen >= count:
                    yield item
                else:
                    seen += 1

        return Stream(_gen())

    return _op


_MERGE_ITEM = object()
_MERGE_END = object()
_MERGE_ERROR = object()


def merge(*sources: EventStream[Any]) -> Any:
    """Interleave items from multiple source streams.

    The first feed error cancels the remaining feeds and is re-raised to
    the consumer; items already emitted stay emitted.

    Args:
        sources: Additional streams to merge with the piped source.

    Returns:
        An operator merging the piped source with all given sources.
    """

    def _op(source: EventStream[Any]) -> EventStream[Any]:
        all_sources = (source, *sources)

        async def _gen() -> AsyncIterator[Any]:
            queue: asyncio.Queue[tuple[object, Any]] = asyncio.Queue()
            remaining = len(all_sources)

            async def _feed(stream: EventStream[Any]) -> None:
                nonlocal remaining
                try:
                    async for item in stream:
                        await queue.put((_MERGE_ITEM, item))
                except Exception as exc:  # noqa: BLE001 — operator boundary
                    await queue.put((_MERGE_ERROR, exc))
                finally:
                    remaining -= 1
                    if remaining == 0:
                        await queue.put((_MERGE_END, None))

            tasks = [asyncio.create_task(_feed(s)) for s in all_sources]
            self_tasks: set[asyncio.Task[Any]] = set(tasks)
            for task in tasks:
                self_tasks.add(task)  # keep a strong ref (RUF006)
                task.add_done_callback(self_tasks.discard)
            try:
                while True:
                    kind, payload = await queue.get()
                    if kind is _MERGE_ITEM:
                        yield payload
                    elif kind is _MERGE_ERROR:
                        raise payload
                    else:
                        break
            finally:
                for task in tasks:
                    task.cancel()
                for task in tasks:
                    with suppress(asyncio.CancelledError):
                        await task

        return Stream(_gen())

    return _op


def catch(
    fallback: Callable[[BaseException], EventStream[Any]] | None = None,
    default: Any = None,
) -> Any:
    """Handle a source error by switching to a fallback or emitting a default.

    Args:
        fallback: Optional callable building a replacement stream from the error.
        default: Value emitted once before the stream ends when no fallback given.

    Returns:
        An operator that recovers from the first downstream error.
    """

    def _op(source: EventStream[Any]) -> EventStream[Any]:
        async def _gen() -> AsyncIterator[Any]:
            try:
                async for item in source:
                    yield item
            except Exception as exc:  # noqa: BLE001 — operator boundary
                if fallback is not None:
                    replacement = fallback(exc)
                    async for item in replacement:
                        yield item
                elif default is not None:
                    yield default

        return Stream(_gen())

    return _op


def on_end(
    on_complete: Callable[[], Any] | None = None,
    on_error: Callable[[BaseException], Any] | None = None,
) -> Any:
    """Invoke a callback exactly once when the stream completes or errors.

    Callbacks may be sync or async. On error, ``on_error`` runs first and
    the exception still propagates to the consumer afterwards.

    Args:
        on_complete: Called with no arguments on normal completion.
        on_error: Called with the exception on failure.

    Returns:
        An operator that signals stream termination.

    Example:
        ```python
        stream = source.pipe(
            ops.on_end(on_complete=lambda: print("done")),
        )
        ```
    """

    def _op(source: EventStream[Any]) -> EventStream[Any]:
        async def _gen() -> AsyncIterator[Any]:
            try:
                async for item in source:
                    yield item
            except Exception as exc:  # noqa: BLE001 — operator boundary
                if on_error is not None:
                    result = on_error(exc)
                    if inspect.isawaitable(result):
                        await result
                raise
            if on_complete is not None:
                result = on_complete()
                if inspect.isawaitable(result):
                    await result

        return Stream(_gen())

    return _op
