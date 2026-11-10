"""Rate limiter for LLM providers.

Provides TPM (Tokens Per Minute) and RPM (Requests Per Minute) limiting.
"""

from __future__ import annotations

import asyncio

from quadkit.logging import (
    get_logger,
)
from quadkit.primitives import clock as ambient_clock

logger = get_logger(__name__)


class TokenBucket:
    """Token bucket implementation for rate limiting."""

    def __init__(self, capacity: float, refill_rate: float):
        """Initialize bucket.

        Args:
            capacity: Maximum bucket size
            refill_rate: Tokens added per second
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity
        self.last_update = ambient_clock.monotonic()
        self._lock = asyncio.Lock()

    async def consume(self, amount: float = 1.0) -> bool:
        """Attempt to consume tokens from the bucket.

        Args:
            amount: Number of tokens to consume

        Returns:
            True if consumed, False if blocked
        """
        async with self._lock:
            now = ambient_clock.monotonic()
            elapsed = now - self.last_update
            self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
            self.last_update = now

            if self.tokens >= amount:
                self.tokens -= amount
                return True
            return False


class RateLimiter:
    """Rate limiter for LLM requests (RPM and TPM).

    Manages multiple buckets for different models and providers.
    """

    def __init__(self) -> None:
        """Initialize rate limiter."""
        self._buckets: dict[str, TokenBucket] = {}
        self._lock = asyncio.Lock()

    def _get_bucket_key(self, provider: str, model: str, limit_type: str) -> str:
        return f"{provider}:{model}:{limit_type}"

    async def check(
        self,
        provider: str,
        model: str,
        tpm_limit: int | None = None,
        rpm_limit: int | None = None,
        estimated_tokens: int = 0,
    ) -> bool:
        """Check if request is allowed under current limits.

        Args:
            provider: AI provider name
            model: Model name
            tpm_limit: Tokens Per Minute limit
            rpm_limit: Requests Per Minute limit
            estimated_tokens: Estimated tokens in request

        Returns:
            True if allowed, False if blocked
        """
        async with self._lock:
            # Initialize buckets if limits provided
            if rpm_limit:
                key = self._get_bucket_key(provider, model, "rpm")
                if key not in self._buckets:
                    # RPM limit: 60 seconds interval
                    self._buckets[key] = TokenBucket(rpm_limit, rpm_limit / 60.0)

                if not await self._buckets[key].consume(1.0):
                    logger.warning("llm_rate_limit_rpm_reached")
                    return False

            if tpm_limit:
                key = self._get_bucket_key(provider, model, "tpm")
                if key not in self._buckets:
                    # TPM limit: 60 seconds interval
                    self._buckets[key] = TokenBucket(tpm_limit, tpm_limit / 60.0)

                if not await self._buckets[key].consume(float(estimated_tokens)):
                    logger.warning(
                        "llm_rate_limit_tpm_reached",
                        estimated_tokens=estimated_tokens,
                    )
                    return False

        return True

    def __repr__(self) -> str:
        return f"RateLimiter(buckets={len(self._buckets)})"
