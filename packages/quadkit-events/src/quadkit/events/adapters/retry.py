"""Retry utilities for events adapters.

Minimal async retry implementation using stdlib only (asyncio, secrets).
``RetryConfig`` is sourced from ``quadkit.contracts`` so no cross-extension
dependency on ``the optional provider`` is required.
"""

from __future__ import annotations

import asyncio
import secrets
from typing import TYPE_CHECKING, Any, TypeVar

from quadkit.contracts.infra.resilience.models import RetryConfig

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

T = TypeVar("T")


def _calculate_delay(attempt: int, config: RetryConfig) -> float:
    """Return exponential back-off delay with optional jitter for *attempt*."""
    delay = min(config.base_delay * (config.backoff_factor**attempt), config.max_delay)
    if config.jitter:
        jitter_factor = (
            0.25 if isinstance(config.jitter, bool) else float(config.jitter)
        )
        jitter_range = delay * jitter_factor
        delay += secrets.SystemRandom().uniform(-jitter_range, jitter_range)
    return max(0.0, delay)


async def retry(
    func: Callable[..., Awaitable[T]],
    *args: Any,
    config: RetryConfig | None = None,
    **kwargs: Any,
) -> T:
    """Execute *func* with retry logic per *config*.

    Args:
        func: Async callable to execute.
        *args: Positional arguments forwarded to *func*.
        config: Retry configuration; defaults to ``RetryConfig()`` (3 attempts).
        **kwargs: Keyword arguments forwarded to *func*.

    Returns:
        The first successful return value of *func*.

    Raises:
        Exception: The last exception raised after all attempts are exhausted.
    """
    cfg = config or RetryConfig()
    last_exc: Exception | None = None

    for attempt in range(cfg.max_attempts):
        try:
            return await func(*args, **kwargs)
        except cfg.retry_on as exc:
            if cfg.retry_if is not None and not cfg.retry_if(exc):
                raise
            last_exc = exc
            if attempt + 1 == cfg.max_attempts:
                raise last_exc
            if cfg.on_retry:
                cfg.on_retry(attempt + 1, exc)
            await asyncio.sleep(_calculate_delay(attempt, cfg))

    if last_exc is not None:
        raise last_exc
    raise RuntimeError("Retry exhausted without exception")


__all__ = ["RetryConfig", "retry"]
