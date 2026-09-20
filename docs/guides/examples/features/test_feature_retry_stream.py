"""Feature tour: reactive retry over streams.

`stream.pipe(retry(RetryOptions(...)))` re-subscribes to a flaky source until
the attempt budget is spent — only the successful attempt's items are
emitted. The contract is one honest sentence: the source must be
*re-subscribable*. Streams are cold single-pass iterators by design, so a
poller wires its generator *factory* into a tiny replayable subclass — after
that, backoff, attempt limits, and a `should_retry` predicate are one import.
"""

from collections.abc import AsyncIterator, Callable
from typing import TypeVar

import pytest

from quadkit import RetryOptions, retry
from quadkit.reactive import EventStream, Stream

T = TypeVar("T")


class TransientBackendError(Exception):
    """Retryable: the upstream flakes and recovers."""


class CredentialError(Exception):
    """Fatal: retrying will never help."""


class ResubscribableSource(Stream[T]):
    """A stream whose every subscription re-runs the producing factory.

    This is the "replayable" contract `retry()` requires: `pipe` (inherited)
    composes operators, and `__aiter__` hands out a fresh generator per
    attempt instead of reviving the exhausted one.
    """

    def __init__(self, factory: Callable[[], AsyncIterator[T]]) -> None:
        self._factory = factory
        super().__init__(factory())

    def __aiter__(self) -> AsyncIterator[T]:
        return self._factory()


def make_flaky_polling(
    attempts_log: list[int],
    failures_before_success: int,
) -> EventStream[str]:
    """A polling source that fails its first N subscriptions."""

    calls = 0

    def produce() -> AsyncIterator[str]:
        async def gen() -> AsyncIterator[str]:
            nonlocal calls
            calls += 1
            attempts_log.append(calls)
            if calls <= failures_before_success:
                raise TransientBackendError(f"flake {calls}")
            yield f"reading#{calls}"
            yield f"confirmed#{calls}"

        return gen()

    return ResubscribableSource(produce)


@pytest.mark.asyncio
async def test_retry_recovers_after_transient_failures() -> None:
    attempts: list[int] = []
    polled = make_flaky_polling(attempts, failures_before_success=2)

    recovered = polled.pipe(
        retry(RetryOptions(max_attempts=3, delay=0.0)),
    )

    readings = [item async for item in recovered]

    assert attempts == [1, 2, 3]
    assert readings == ["reading#3", "confirmed#3"]


@pytest.mark.asyncio
async def test_retry_exhausts_budget_and_surfaces_last_error() -> None:
    attempts: list[int] = []
    polled = make_flaky_polling(attempts, failures_before_success=99)

    recovered = polled.pipe(
        retry(RetryOptions(max_attempts=2, delay=0.0)),
    )

    with pytest.raises(TransientBackendError, match="flake 2"):
        _ = [item async for item in recovered]
    assert attempts == [1, 2]


@pytest.mark.asyncio
async def test_should_retry_short_circuits_fatal_errors() -> None:
    attempts: list[int] = []

    async def doomed() -> AsyncIterator[str]:
        attempts.append(1)
        raise CredentialError("invalid token")
        yield  # unused: marks this an async generator

    recovered = ResubscribableSource(doomed).pipe(
        retry(
            RetryOptions(
                max_attempts=5,
                delay=0.0,
                should_retry=lambda exc: isinstance(exc, TransientBackendError),
            )
        ),
    )

    with pytest.raises(CredentialError):
        _ = [item async for item in recovered]
    assert attempts == [1]  # no pointless retries against a fatal error
