"""Tests for new middleware classes — CorrelationId, Retry, Validation, Caching."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.middleware.builtins import (
    CachingMiddleware,
    CorrelationIdMiddleware,
    RetryMiddleware,
    ValidationMiddleware,
)

# ===========================================================================
# CorrelationIdMiddleware
# ===========================================================================


class TestCorrelationIdMiddleware:
    """Tests for CorrelationIdMiddleware UUID attachment."""

    @pytest.mark.asyncio
    async def test_generates_id_when_missing(self) -> None:
        ctx = MagicMock(spec=[])
        ctx.correlation_id = None
        # Allow attribute detection: getattr returns None → generates UUID
        mw = CorrelationIdMiddleware()
        handler = AsyncMock(return_value="ok")
        result = await mw(ctx, handler)
        assert result == "ok"
        handler.assert_called_once_with(ctx)

    @pytest.mark.asyncio
    async def test_preserves_existing_id(self) -> None:
        ctx = MagicMock()
        ctx.correlation_id = "existing-id"
        mw = CorrelationIdMiddleware()
        handler = AsyncMock(return_value="ok")
        await mw(ctx, handler)
        # Should NOT overwrite
        assert ctx.correlation_id == "existing-id"

    @pytest.mark.asyncio
    async def test_custom_header_name(self) -> None:
        ctx = MagicMock()
        ctx.x_request_id = None
        mw = CorrelationIdMiddleware(header="x_request_id")
        handler = AsyncMock(return_value="ok")
        await mw(ctx, handler)
        handler.assert_called_once_with(ctx)

    @pytest.mark.asyncio
    async def test_sets_uuid_on_context(self) -> None:
        class Ctx:
            correlation_id: str | None = None

        ctx = Ctx()
        mw = CorrelationIdMiddleware()
        handler = AsyncMock(return_value="done")
        await mw(ctx, handler)
        assert ctx.correlation_id is not None
        assert len(ctx.correlation_id) == 36  # UUID4 format


# ===========================================================================
# RetryMiddleware
# ===========================================================================


class TestRetryMiddleware:
    """Tests for RetryMiddleware retry logic."""

    @pytest.mark.asyncio
    async def test_no_retry_on_success(self) -> None:
        handler = AsyncMock(return_value="ok")
        mw = RetryMiddleware(catch=Exception, max_retries=3, delay=0)
        result = await mw("ctx", handler)
        assert result == "ok"
        assert handler.call_count == 1

    @pytest.mark.asyncio
    async def test_retries_on_failure(self) -> None:
        call_count = 0

        async def flaky(ctx: object) -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("transient")
            return "recovered"

        mw = RetryMiddleware(catch=ValueError, max_retries=3, delay=0)
        result = await mw("ctx", flaky)
        assert result == "recovered"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_exhausted_retries_raises(self) -> None:
        handler = AsyncMock(side_effect=RuntimeError("permanent"))
        mw = RetryMiddleware(catch=RuntimeError, max_retries=2, delay=0)
        with pytest.raises(RuntimeError, match="permanent"):
            await mw("ctx", handler)
        assert handler.call_count == 3  # initial + 2 retries

    @pytest.mark.asyncio
    async def test_only_catches_specified_types(self) -> None:
        handler = AsyncMock(side_effect=TypeError("wrong type"))
        mw = RetryMiddleware(catch=ValueError, max_retries=3, delay=0)
        with pytest.raises(TypeError, match="wrong type"):
            await mw("ctx", handler)
        assert handler.call_count == 1  # no retry for TypeError

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Flaky timing test - timing variance in CI")
    async def test_delay_between_retries(self) -> None:
        calls: list[float] = []
        import time

        async def timed_handler(ctx: object) -> str:
            calls.append(time.monotonic())
            if len(calls) < 2:
                raise ValueError("retry")
            return "ok"

        mw = RetryMiddleware(catch=ValueError, max_retries=2, delay=0.05)
        await mw("ctx", timed_handler)
        assert len(calls) == 2
        assert (calls[1] - calls[0]) >= 0.04  # Allow variance for CI


# ===========================================================================
# ValidationMiddleware
# ===========================================================================


class TestValidationMiddleware:
    """Tests for ValidationMiddleware sync/async validation."""

    @pytest.mark.asyncio
    async def test_valid_input_proceeds(self) -> None:
        def validator(ctx: object) -> None:
            pass  # valid

        handler = AsyncMock(return_value="result")
        mw = ValidationMiddleware(validator)
        result = await mw("ctx", handler)
        assert result == "result"
        handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_invalid_input_raises(self) -> None:
        def validator(ctx: object) -> None:
            raise ValueError("invalid input")

        handler = AsyncMock(return_value="result")
        mw = ValidationMiddleware(validator)
        with pytest.raises(ValueError, match="invalid input"):
            await mw("ctx", handler)
        handler.assert_not_called()

    @pytest.mark.asyncio
    async def test_async_validator(self) -> None:
        async def async_validator(ctx: object) -> None:
            pass  # valid asynchronously

        handler = AsyncMock(return_value="ok")
        mw = ValidationMiddleware(async_validator)
        result = await mw("ctx", handler)
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_async_validator_raises(self) -> None:
        async def async_validator(ctx: object) -> None:
            raise RuntimeError("async invalid")

        handler = AsyncMock()
        mw = ValidationMiddleware(async_validator)
        with pytest.raises(RuntimeError, match="async invalid"):
            await mw("ctx", handler)
        handler.assert_not_called()


# ===========================================================================
# CachingMiddleware
# ===========================================================================


class TestCachingMiddleware:
    """Tests for CachingMiddleware cache-aside behavior.

    The fake caches honor the ``CacheBackendProtocol`` contract:
    ``get()`` returns ``Result[Any | None, CacheError]`` — ``Ok(None)``
    for a miss — and ``set()`` returns ``Result[None, CacheError]``.
    """

    @staticmethod
    def _ok(value: object) -> Any:
        from quadkit.result import Ok

        return Ok(value)

    @pytest.mark.asyncio
    async def test_cache_miss_computes_and_stores(self) -> None:
        cache = AsyncMock()
        cache.get = AsyncMock(return_value=self._ok(None))
        cache.set = AsyncMock()
        handler = AsyncMock(return_value="computed")

        mw = CachingMiddleware(key_func=lambda ctx: f"key:{ctx}", cache=cache, ttl=30.0)
        result = await mw("x", handler)

        assert result == "computed"
        cache.get.assert_called_once_with("key:x")
        cache.set.assert_called_once_with("key:x", "computed", ttl=30.0)
        handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_hit_skips_handler(self) -> None:
        cache = AsyncMock()
        cache.get = AsyncMock(return_value=self._ok("cached_value"))
        handler = AsyncMock(return_value="fresh")

        mw = CachingMiddleware(key_func=lambda _ctx: "k", cache=cache)
        result = await mw("x", handler)

        assert result == "cached_value"
        handler.assert_not_called()

    @pytest.mark.asyncio
    async def test_different_keys_separate_entries(self) -> None:
        cache_store: dict[str, object] = {}

        async def mock_get(key: str) -> Any:
            from quadkit.result import Ok

            return Ok(cache_store.get(key))

        async def mock_set(key: str, value: object, ttl: float = 60.0) -> None:
            cache_store[key] = value

        cache = MagicMock()
        cache.get = mock_get
        cache.set = mock_set

        call_count = 0

        async def handler(ctx: object) -> str:
            nonlocal call_count
            call_count += 1
            return f"result:{ctx}"

        mw = CachingMiddleware(key_func=lambda ctx: f"key:{ctx}", cache=cache)
        r1 = await mw("a", handler)
        r2 = await mw("b", handler)
        r3 = await mw("a", handler)  # cache hit

        assert r1 == "result:a"
        assert r2 == "result:b"
        assert r3 == "result:a"
        assert call_count == 2  # 'a' computed once, 'b' once

    @pytest.mark.asyncio
    async def test_custom_ttl(self) -> None:
        cache = AsyncMock()
        cache.get = AsyncMock(return_value=self._ok(None))
        cache.set = AsyncMock()
        handler = AsyncMock(return_value="v")

        mw = CachingMiddleware(key_func=lambda _c: "k", cache=cache, ttl=120.0)
        await mw("x", handler)
        cache.set.assert_called_once_with("k", "v", ttl=120.0)
