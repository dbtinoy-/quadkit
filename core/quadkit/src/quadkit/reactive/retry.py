"""Retry operator with configurable backoff."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any

from quadkit.reactive.core import EventStream, Stream


@dataclass(frozen=True)
class RetryOptions:
    """Configuration for the retry operator.

    Attributes:
        max_attempts: Maximum number of subscription attempts. Defaults to 3.
        delay: Base delay before retrying, in seconds. Defaults to 0.
        backoff: ``"fixed"`` or ``"exponential"``. Defaults to ``"exponential"``.
        max_delay: Upper bound for exponential backoff. Defaults to 30.
        should_retry: Optional predicate; retry only when it returns True.
        clock: Optional time source for backoff waits.
    """

    max_attempts: int = 3
    delay: float = 0.0
    backoff: str = "exponential"
    max_delay: float = 30.0
    should_retry: Callable[[BaseException], bool] | None = None
    clock: Callable[[], float] | None = None


def retry(options: RetryOptions | None = None) -> Any:
    """Re-subscribe to the source on error until attempts are exhausted.

    Args:
        options: Retry configuration; defaults to ``RetryOptions()``.

    Returns:
        An operator that retries the piped source.

    Note:
        Only the successful attempt's output is emitted; failed attempts
        are discarded. The source must be re-subscribable (replayable) for
        retries to take effect — single-pass ``Stream`` sources are not.
    """

    opts = options or RetryOptions()

    def _op(source: EventStream[Any]) -> EventStream[Any]:
        async def _gen() -> AsyncIterator[Any]:
            attempt = 0
            while attempt < opts.max_attempts:
                attempt += 1
                session: list[Any] = []
                try:
                    async for item in source:
                        session.append(item)
                    for item in session:
                        yield item
                    return
                except Exception as exc:  # noqa: BLE001 — operator boundary
                    if opts.should_retry is not None and not opts.should_retry(exc):
                        raise
                    if attempt >= opts.max_attempts:
                        raise
                    await _backoff_sleep(opts, attempt)

        return Stream(_gen())

    return _op


async def _backoff_sleep(opts: RetryOptions, attempt: int) -> None:
    """Sleep according to the backoff policy."""
    if opts.backoff == "fixed":
        wait = opts.delay
    else:
        wait = min(opts.delay * (2 ** (attempt - 1)), opts.max_delay)
    if wait <= 0:
        return
    await asyncio.sleep(wait)
