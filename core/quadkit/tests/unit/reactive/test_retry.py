"""Tests for the retry operator."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from typing import Any

import pytest

from quadkit.reactive import EventStream, Op, Stream
from quadkit.reactive.retry import RetryOptions, retry


class ReplayingStream(EventStream[Any]):
    """EventStream that rebuilds its source on every subscription (retry fixture)."""

    def __init__(self, factory: Callable[[], AsyncIterator[Any]]) -> None:
        self._factory = factory

    def pipe(self, *operators: Op[Any, Any]) -> EventStream[Any]:
        result: EventStream[Any] = self
        for operator in operators:
            result = operator(result)
        return result

    def __aiter__(self) -> AsyncIterator[Any]:
        return self._factory()


async def collect(stream: EventStream[Any]) -> list[Any]:
    return [item async for item in stream]


async def test_retry_resubscribes_on_failure() -> None:
    attempts = 0

    def flaky() -> AsyncIterator[Any]:
        async def _gen() -> Any:
            nonlocal attempts
            attempts += 1
            yield 1
            if attempts < 3:
                raise RuntimeError("flaky")
            yield 2

        return _gen()

    stream = ReplayingStream(flaky).pipe(
        retry(RetryOptions(max_attempts=3, delay=0.0, backoff="fixed"))
    )
    assert await collect(stream) == [1, 2]
    assert attempts == 3


async def test_retry_gives_up_and_raises_last_error() -> None:
    def always_fails() -> AsyncIterator[Any]:
        async def _gen() -> Any:
            raise RuntimeError("nope")
            yield  # unreachable; makes this an async generator

        return _gen()

    stream = ReplayingStream(always_fails).pipe(
        retry(RetryOptions(max_attempts=2, delay=0.0))
    )
    with pytest.raises(RuntimeError, match="nope"):
        await collect(stream)


async def test_retry_should_retry_predicate_skips() -> None:
    def boom() -> AsyncIterator[Any]:
        async def _gen() -> Any:
            raise ValueError("skip me")
            yield  # unreachable; makes this an async generator

        return _gen()

    stream = ReplayingStream(boom).pipe(
        retry(
            RetryOptions(
                max_attempts=3,
                delay=0.0,
                should_retry=lambda e: not isinstance(e, ValueError),
            )
        )
    )
    with pytest.raises(ValueError, match="skip me"):
        await collect(stream)