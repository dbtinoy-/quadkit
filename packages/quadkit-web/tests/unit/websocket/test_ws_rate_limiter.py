"""Unit tests for WebSocketRateLimiter (M46)."""

from __future__ import annotations

import asyncio

import pytest

from quadkit.web.websocket.rate_limiter import WebSocketRateLimiter


class TestWebSocketRateLimiter:
    """WebSocketRateLimiter throttles messages using a per-connection token bucket."""

    # -- construction --

    def test_raises_on_non_positive_rate(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            WebSocketRateLimiter(max_messages_per_second=0)

    def test_raises_on_negative_rate(self) -> None:
        with pytest.raises(ValueError):
            WebSocketRateLimiter(max_messages_per_second=-1.0)

    def test_initial_active_connection_count_is_zero(self) -> None:
        limiter = WebSocketRateLimiter()
        assert limiter.active_connection_count == 0

    # -- check -- first message allowed --

    @pytest.mark.asyncio
    async def test_first_message_is_allowed(self) -> None:
        limiter = WebSocketRateLimiter(max_messages_per_second=10.0)
        allowed = await limiter.check("conn-1")
        assert allowed is True

    @pytest.mark.asyncio
    async def test_multiple_messages_within_budget_are_allowed(self) -> None:
        limiter = WebSocketRateLimiter(max_messages_per_second=10.0)
        results = [await limiter.check("conn-1") for _ in range(10)]
        assert all(results)

    # -- check -- burst exceeds capacity --

    @pytest.mark.asyncio
    async def test_burst_beyond_capacity_is_rejected(self) -> None:
        limiter = WebSocketRateLimiter(max_messages_per_second=5.0)
        # Drain the bucket (5 tokens)
        for _ in range(5):
            await limiter.check("conn-1")

        # Next one should be rejected
        rejected = await limiter.check("conn-1")
        assert rejected is False

    # -- check -- bucket refills over time --

    @pytest.mark.asyncio
    async def test_bucket_refills_over_time(self) -> None:
        limiter = WebSocketRateLimiter(max_messages_per_second=100.0)
        # Drain completely
        for _ in range(100):
            await limiter.check("conn-1")

        # Wait long enough for at least one token to refill (10ms at 100/s)
        await asyncio.sleep(0.02)

        allowed = await limiter.check("conn-1")
        assert allowed is True

    # -- independent connections --

    @pytest.mark.asyncio
    async def test_connections_have_independent_buckets(self) -> None:
        limiter = WebSocketRateLimiter(max_messages_per_second=2.0)
        # Drain conn-1
        await limiter.check("conn-1")
        await limiter.check("conn-1")

        # conn-2 should still have a full bucket
        allowed = await limiter.check("conn-2")
        assert allowed is True

    # -- remove --

    @pytest.mark.asyncio
    async def test_remove_frees_connection_state(self) -> None:
        limiter = WebSocketRateLimiter(max_messages_per_second=5.0)
        await limiter.check("conn-1")
        assert limiter.active_connection_count == 1

        await limiter.remove("conn-1")

        assert limiter.active_connection_count == 0

    @pytest.mark.asyncio
    async def test_remove_nonexistent_connection_is_safe(self) -> None:
        limiter = WebSocketRateLimiter()
        # Should not raise
        await limiter.remove("ghost")

    # -- connection tracking --

    @pytest.mark.asyncio
    async def test_active_connection_count_tracks_unique_connections(self) -> None:
        limiter = WebSocketRateLimiter(max_messages_per_second=10.0)
        await limiter.check("a")
        await limiter.check("b")
        await limiter.check("a")  # duplicate — not a new connection

        assert limiter.active_connection_count == 2
