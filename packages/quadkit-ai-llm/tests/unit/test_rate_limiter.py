"""Unit tests for RateLimiter and TokenBucket."""

from __future__ import annotations

import pytest

from quadkit.ai.llm.rate_limiting.core import RateLimiter, TokenBucket


class TestTokenBucket:
    @pytest.mark.asyncio
    async def test_consume_within_capacity(self) -> None:
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        assert await bucket.consume(5) is True
        assert bucket.tokens == pytest.approx(5, abs=0.5)

    @pytest.mark.asyncio
    async def test_consume_exceeds_capacity(self) -> None:
        bucket = TokenBucket(capacity=5, refill_rate=1.0)
        assert await bucket.consume(10) is False

    @pytest.mark.asyncio
    async def test_multiple_consumes(self) -> None:
        bucket = TokenBucket(capacity=10, refill_rate=0.0)  # no refill
        assert await bucket.consume(3) is True
        assert await bucket.consume(3) is True
        assert await bucket.consume(3) is True
        assert await bucket.consume(3) is False  # only 1 left

    @pytest.mark.asyncio
    async def test_default_consume_one(self) -> None:
        bucket = TokenBucket(capacity=2, refill_rate=0.0)
        assert await bucket.consume() is True
        assert await bucket.consume() is True
        assert await bucket.consume() is False


class TestRateLimiter:
    @pytest.mark.asyncio
    async def test_check_no_limits(self) -> None:
        rl = RateLimiter()
        result = await rl.check(provider="openai", model="gpt-4")
        assert result is True

    @pytest.mark.asyncio
    async def test_check_rpm_limit_allows(self) -> None:
        rl = RateLimiter()
        result = await rl.check(
            provider="openai", model="gpt-4", rpm_limit=60,
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_check_rpm_limit_blocks(self) -> None:
        rl = RateLimiter()
        # Exhaust RPM: capacity=1, so second call should fail
        await rl.check(provider="openai", model="gpt-4", rpm_limit=1)
        result = await rl.check(provider="openai", model="gpt-4", rpm_limit=1)
        assert result is False

    @pytest.mark.asyncio
    async def test_check_tpm_limit_allows(self) -> None:
        rl = RateLimiter()
        result = await rl.check(
            provider="openai", model="gpt-4",
            tpm_limit=10000, estimated_tokens=500,
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_check_tpm_limit_blocks(self) -> None:
        rl = RateLimiter()
        result = await rl.check(
            provider="openai", model="gpt-4",
            tpm_limit=100, estimated_tokens=200,
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_repr(self) -> None:
        rl = RateLimiter()
        assert "RateLimiter" in repr(rl)
        await rl.check(provider="openai", model="gpt-4", rpm_limit=60)
        assert "buckets=1" in repr(rl)
