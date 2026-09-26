"""Rate limiting for task execution.

Provides token bucket rate limiting for controlling task throughput.
Uses only stdlib/asyncio — no cross-extension imports.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from quadkit.primitives import clock as ambient_clock


class TokenBucket:
    """Async token bucket rate limiter.

    Implements the token-bucket algorithm: tokens are added at a fixed
    *refill_rate* (tokens per second) up to *capacity*, and each
    :meth:`acquire` call consumes one or more tokens.

    Args:
        capacity: Maximum number of tokens the bucket can hold.
        refill_rate: Tokens added per second.
        initial_tokens: Starting token count (defaults to *capacity*).
    """

    def __init__(
        self,
        capacity: float,
        refill_rate: float,
        initial_tokens: float | None = None,
    ) -> None:
        self.capacity = float(capacity)
        self.refill_rate = float(refill_rate)
        self._tokens: float = float(
            initial_tokens if initial_tokens is not None else capacity
        )
        self._last_refill = ambient_clock.monotonic()
        self._lock = asyncio.Lock()

    def _refill(self) -> None:
        """Add tokens proportional to elapsed time since last refill."""
        now = ambient_clock.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self.capacity, self._tokens + elapsed * self.refill_rate)
        self._last_refill = now

    async def acquire(self, tokens: int = 1) -> None:
        """Block until *tokens* are available in the bucket.

        Args:
            tokens: Number of tokens to consume (default 1).

        Raises:
            ValueError: If *tokens* exceeds :attr:`capacity`.
        """
        if tokens > self.capacity:
            msg = "Cannot acquire more tokens than bucket capacity"
            raise ValueError(msg)

        while True:
            async with self._lock:
                self._refill()
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return
                wait_time = (tokens - self._tokens) / self.refill_rate
            await asyncio.sleep(wait_time)

    async def try_acquire(self, tokens: int = 1) -> bool:
        """Non-blocking token acquisition.

        Args:
            tokens: Number of tokens to consume (default 1).

        Returns:
            ``True`` if the tokens were acquired; ``False`` if insufficient.
        """
        async with self._lock:
            self._refill()
            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False

    @property
    def available_tokens(self) -> float:
        """Current number of available tokens (snapshot, not thread-safe)."""
        return self._tokens


@dataclass
class QueueRateLimiter:
    """Per-queue rate limiter.

    Manages independent rate limits for named task queues, delegating each
    limit to a :class:`TokenBucket`.

    Example::

        limiter = QueueRateLimiter()
        limiter.add_limit("emails", rate=5, per=1.0)   # 5 / sec
        limiter.add_limit("reports", rate=1, per=60.0) # 1 / min

        await limiter.acquire("emails")
    """

    _limits: dict[str, TokenBucket] = field(default_factory=dict, init=False)

    def add_limit(
        self,
        queue: str,
        rate: int,
        per: float = 1.0,
        burst: int | None = None,
    ) -> None:
        """Register a rate limit for a named queue.

        Args:
            queue: Queue name to apply the limit to.
            rate: Allowed requests per time period.
            per: Length of the time period in seconds.
            burst: Maximum burst size (defaults to *rate*).
        """
        burst_size = burst if burst is not None else rate
        self._limits[queue] = TokenBucket(
            capacity=float(burst_size),
            refill_rate=rate / per,
        )

    async def acquire(self, queue: str) -> None:
        """Block until a token is available for *queue*.

        Args:
            queue: Queue name; a no-op for unlisted queues.
        """
        if queue in self._limits:
            await self._limits[queue].acquire()

    async def try_acquire(self, queue: str) -> bool:
        """Attempt a non-blocking token acquisition for *queue*.

        Args:
            queue: Queue name.

        Returns:
            ``True`` if a token was obtained or the queue has no limit;
            ``False`` if the queue is currently rate-limited.
        """
        if queue in self._limits:
            return await self._limits[queue].try_acquire()
        return True


class GlobalRateLimiter:
    """System-wide throughput cap applied across all queues.

    Delegates to a single :class:`TokenBucket`
    for consistent rate enforcement regardless of which queue a task
    originates from.

    Example::

        limiter = GlobalRateLimiter(rate=100, per=1.0)  # 100 tasks / sec
        await limiter.acquire()
    """

    def __init__(self, rate: int, per: float = 1.0, burst: int | None = None) -> None:
        """Initialise the global rate limiter.

        Args:
            rate: Maximum allowed tasks per time period.
            per: Length of the time period in seconds.
            burst: Maximum burst capacity (defaults to *rate*).
        """
        burst_size = burst if burst is not None else rate
        self._bucket = TokenBucket(
            capacity=float(burst_size),
            refill_rate=rate / per,
        )

    async def acquire(self) -> None:
        """Block until a global token is available."""
        await self._bucket.acquire()

    async def try_acquire(self) -> bool:
        """Non-blocking global token acquisition.

        Returns:
            ``True`` if a token was obtained; ``False`` if globally rate-limited.
        """
        return await self._bucket.try_acquire()


__all__ = [
    "GlobalRateLimiter",
    "QueueRateLimiter",
]
