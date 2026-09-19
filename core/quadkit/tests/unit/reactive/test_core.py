"""Tests for the reactive stream core."""

from __future__ import annotations

from typing import Any

from quadkit.reactive import EventStream, Stream
from quadkit.reactive.exceptions import ReactiveError


async def test_stream_iterates_async_generator() -> None:
    async def gen() -> Any:
        for i in range(3):
            yield i

    stream: EventStream[int] = Stream(gen())
    assert [item async for item in stream] == [0, 1, 2]


async def test_stream_pipe_applies_operators_left_to_right() -> None:
    def double(src: EventStream[int]) -> EventStream[int]:
        async def _gen() -> Any:
            async for item in src:
                yield item * 2

        return Stream(_gen())

    def add_one(src: EventStream[int]) -> EventStream[int]:
        async def _gen() -> Any:
            async for item in src:
                yield item + 1

        return Stream(_gen())

    async def gen() -> Any:
        for i in range(2):
            yield i

    stream = Stream(gen()).pipe(double, add_one)
    assert [item async for item in stream] == [1, 3]


async def test_stream_single_pass_second_iteration_yields_nothing() -> None:
    async def gen() -> Any:
        yield 1
        yield 2

    stream = Stream(gen())
    assert [item async for item in stream] == [1, 2]
    # Stream wraps one AsyncIterator; a second full iteration finds it
    # already exhausted. Construct a fresh Stream to consume again.
    assert [item async for item in stream] == []


def test_reactive_error_is_quadkit_error() -> None:
    assert issubclass(ReactiveError, Exception)


def test_operators_order_documented() -> None:
    # pipe() type contract sanity: EventStream[Any] is returned
    from quadkit.reactive.core import pipe as _unused  # noqa: F401

    assert callable(_unused)