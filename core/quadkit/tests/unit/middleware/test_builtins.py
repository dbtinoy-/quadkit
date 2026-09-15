"""Unit tests for common middleware implementations."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.middleware.builtins import (
    CachingMiddleware,
    CircuitBreakerMiddleware,
    ConditionalMiddleware,
    CorrelationIdMiddleware,
    ErrorHandlerMiddleware,
    LoggingMiddleware,
    RateLimiterMiddleware,
    TimeoutMiddleware,
    TimingMiddleware,
    ValidationMiddleware,
)
from quadkit.middleware.exceptions import (
    MiddlewareCircuitOpenError,
    MiddlewareRateLimitError,
    MiddlewareTimeoutError,
)


async def passthrough(ctx: Any) -> Any:
    return ctx


class TestTimingMiddleware:
    """Tests for TimingMiddleware."""

    @pytest.mark.asyncio
    async def test_timing_middleware_init(self) -> None:
        """Test timing middleware can be initialized."""
        middleware = TimingMiddleware()
        assert middleware._name == "timing"

    @pytest.mark.asyncio
    async def test_timing_middleware_custom_name(self) -> None:
        """Test timing middleware with custom name."""
        middleware = TimingMiddleware(name="custom_timing")
        assert middleware._name == "custom_timing"

    @pytest.mark.asyncio
    async def test_timing_middleware_measures_time(self) -> None:
        """Test timing middleware measures execution time."""
        middleware = TimingMiddleware()
        next_handler = AsyncMock(return_value="result")

        result = await middleware({}, next_handler)

        assert result == "result"
        next_handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_timing_middleware_on_error(self) -> None:
        """Test timing middleware measures time even on error."""
        middleware = TimingMiddleware()
        next_handler = AsyncMock(side_effect=ValueError("test error"))

        with pytest.raises(ValueError):
            await middleware({}, next_handler)


class TestLoggingMiddleware:
    """Tests for LoggingMiddleware."""

    @pytest.mark.asyncio
    async def test_logging_middleware_init(self) -> None:
        """Test logging middleware can be initialized."""
        middleware = LoggingMiddleware()
        assert middleware._name == "logging"

    @pytest.mark.asyncio
    async def test_logging_middleware_custom_name(self) -> None:
        """Test logging middleware with custom name."""
        middleware = LoggingMiddleware(name="custom_log")
        assert middleware._name == "custom_log"

    @pytest.mark.asyncio
    async def test_logging_middleware_calls_next(self) -> None:
        """Test logging middleware calls next handler."""
        middleware = LoggingMiddleware()
        next_handler = AsyncMock(return_value="result")

        result = await middleware({}, next_handler)

        assert result == "result"
        next_handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_logging_middleware_propagates_error(self) -> None:
        """Test logging middleware propagates exceptions."""
        middleware = LoggingMiddleware()
        next_handler = AsyncMock(side_effect=ValueError("test error"))

        with pytest.raises(ValueError):
            await middleware({}, next_handler)


class TestErrorHandlerMiddleware:
    """Tests for ErrorHandlerMiddleware."""

    def test_error_handler_init(self) -> None:
        """Test error handler middleware can be initialized."""
        middleware = ErrorHandlerMiddleware(catch=(ValueError,))
        assert ValueError in middleware._catch

    @pytest.mark.asyncio
    async def test_error_handler_returns_fallback(self) -> None:
        """Test error handler returns fallback value."""
        middleware = ErrorHandlerMiddleware(
            catch=(ValueError,),
            fallback="fallback_value",
        )
        next_handler = AsyncMock(side_effect=ValueError("test error"))

        result = await middleware({}, next_handler)

        assert result == "fallback_value"

    @pytest.mark.asyncio
    async def test_error_handler_calls_error_handler(self) -> None:
        """Test error handler calls custom error handler."""
        error_handler = AsyncMock(return_value="handled")
        middleware = ErrorHandlerMiddleware(
            catch=(ValueError,),
            error_handler=error_handler,
        )
        next_handler = AsyncMock(side_effect=ValueError("test error"))

        result = await middleware({}, next_handler)

        assert result == "handled"
        error_handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_error_handler_propagates_uncatchable(self) -> None:
        """Test error handler propagates non-matching exceptions."""
        middleware = ErrorHandlerMiddleware(catch=(ValueError,))
        next_handler = AsyncMock(side_effect=TypeError("test error"))

        with pytest.raises(TypeError):
            await middleware({}, next_handler)

    @pytest.mark.asyncio
    async def test_error_handler_passes_through_on_success(self) -> None:
        """Test error handler passes through on success."""
        middleware = ErrorHandlerMiddleware(
            catch=(ValueError,),
            fallback="fallback",
        )
        next_handler = AsyncMock(return_value="success")

        result = await middleware({}, next_handler)

        assert result == "success"


class TestCorrelationIdMiddleware:
    """Tests for CorrelationIdMiddleware."""

    def test_correlation_middleware_init(self) -> None:
        """Test correlation middleware can be initialized."""
        middleware = CorrelationIdMiddleware()
        assert middleware._header == "correlation_id"

    def test_correlation_middleware_custom_header(self) -> None:
        """Test correlation middleware with custom header."""
        middleware = CorrelationIdMiddleware(header="X-Request-ID")
        assert middleware._header == "X-Request-ID"

    @pytest.mark.asyncio
    async def test_correlation_middleware_calls_next(self) -> None:
        """Test correlation middleware calls next handler."""
        middleware = CorrelationIdMiddleware()
        context = {}
        next_handler = AsyncMock()

        await middleware(context, next_handler)

        next_handler.assert_called_once()


class TestValidationMiddleware:
    """Tests for ValidationMiddleware."""

    def test_validation_middleware_init(self) -> None:
        """Test validation middleware can be initialized."""
        validator = AsyncMock()
        middleware = ValidationMiddleware(validator=validator)
        assert middleware._validator == validator


class TestCachingMiddleware:
    """Tests for CachingMiddleware."""

    def test_caching_middleware_init(self) -> None:
        """Test caching middleware can be initialized."""
        key_func = MagicMock()
        cache = MagicMock()
        middleware = CachingMiddleware(key_func=key_func, cache=cache)
        assert middleware._key_func == key_func
        assert middleware._cache == cache


class TestTimeoutMiddleware:
    @pytest.mark.asyncio
    async def test_passes_through_when_fast(self) -> None:
        async def fast_handler(ctx: Any) -> str:
            return "ok"

        mw = TimeoutMiddleware(timeout=5.0)
        result = await mw({"request": "test"}, fast_handler)
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_raises_timeout_error_when_slow(self) -> None:
        async def slow_handler(ctx: Any) -> str:
            await asyncio.sleep(10)
            return "never"

        mw = TimeoutMiddleware(timeout=0.01)
        with pytest.raises(MiddlewareTimeoutError):
            await mw({"request": "test"}, slow_handler)

    @pytest.mark.asyncio
    async def test_custom_name(self) -> None:
        mw = TimeoutMiddleware(timeout=1.0, name="api_timeout")
        assert mw._name == "api_timeout"

    @pytest.mark.asyncio
    async def test_preserves_original_exception_as_cause(self) -> None:
        async def slow_handler(ctx: Any) -> str:
            await asyncio.sleep(10)
            return "never"

        mw = TimeoutMiddleware(timeout=0.01)
        with pytest.raises(MiddlewareTimeoutError) as exc_info:
            await mw({}, slow_handler)
        assert exc_info.value.__cause__ is not None
        assert isinstance(exc_info.value.__cause__, asyncio.TimeoutError)


class TestCircuitBreakerMiddleware:
    @pytest.mark.asyncio
    async def test_closed_state_passes_through(self) -> None:
        async def handler(ctx: Any) -> str:
            return "ok"

        mw = CircuitBreakerMiddleware(failure_threshold=3, recovery_timeout=1.0)
        result = await mw({}, handler)
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_opens_after_threshold_failures(self) -> None:
        call_count = 0

        async def failing_handler(ctx: Any) -> str:
            nonlocal call_count
            call_count += 1
            raise ValueError("boom")

        mw = CircuitBreakerMiddleware(failure_threshold=3, recovery_timeout=60.0)

        for _ in range(3):
            with pytest.raises(ValueError):
                await mw({}, failing_handler)

        assert call_count == 3

        # Circuit should be open now — rejects without calling handler
        with pytest.raises(MiddlewareCircuitOpenError):
            await mw({}, failing_handler)
        assert call_count == 3  # handler was NOT called

    @pytest.mark.asyncio
    async def test_half_open_allows_probe(self) -> None:
        attempt = 0

        async def handler(ctx: Any) -> str:
            nonlocal attempt
            attempt += 1
            return "recovered"

        mw = CircuitBreakerMiddleware(failure_threshold=1, recovery_timeout=0.01)

        # Trip the breaker
        async def fail(ctx: Any) -> str:
            raise ValueError("boom")

        with pytest.raises(ValueError):
            await mw({}, fail)

        # Wait for recovery timeout
        await asyncio.sleep(0.02)

        # Should allow probe request (half-open)
        result = await mw({}, handler)
        assert result == "recovered"
        assert attempt == 1

    @pytest.mark.asyncio
    async def test_half_open_failure_reopens(self) -> None:
        mw = CircuitBreakerMiddleware(failure_threshold=1, recovery_timeout=0.01)

        async def fail(ctx: Any) -> str:
            raise ValueError("boom")

        # Trip the breaker
        with pytest.raises(ValueError):
            await mw({}, fail)

        await asyncio.sleep(0.02)

        # Half-open probe also fails — should re-open
        with pytest.raises(ValueError):
            await mw({}, fail)

        # Should be open again — immediate rejection
        with pytest.raises(MiddlewareCircuitOpenError):
            await mw({}, fail)

    @pytest.mark.asyncio
    async def test_success_resets_failure_count(self) -> None:
        call_count = 0

        async def alternating(ctx: Any) -> str:
            nonlocal call_count
            call_count += 1
            if call_count % 2 == 1:
                raise ValueError("odd failure")
            return "even success"

        mw = CircuitBreakerMiddleware(failure_threshold=3, recovery_timeout=60.0)

        with pytest.raises(ValueError):
            await mw({}, alternating)  # fail (count=1)
        await mw({}, alternating)  # success (resets count)
        with pytest.raises(ValueError):
            await mw({}, alternating)  # fail (count=1 again)
        result = await mw({}, alternating)
        assert result == "even success"


class TestRateLimiterMiddleware:
    @pytest.mark.asyncio
    async def test_allows_within_limit(self) -> None:
        async def handler(ctx: Any) -> str:
            return "ok"

        mw = RateLimiterMiddleware(max_requests=5, window_seconds=60.0)
        for _ in range(5):
            result = await mw({}, handler)
            assert result == "ok"

    @pytest.mark.asyncio
    async def test_rejects_over_limit(self) -> None:
        async def handler(ctx: Any) -> str:
            return "ok"

        mw = RateLimiterMiddleware(max_requests=2, window_seconds=60.0)
        await mw({}, handler)
        await mw({}, handler)
        with pytest.raises(MiddlewareRateLimitError):
            await mw({}, handler)

    @pytest.mark.asyncio
    async def test_refills_after_window(self) -> None:
        async def handler(ctx: Any) -> str:
            return "ok"

        mw = RateLimiterMiddleware(max_requests=1, window_seconds=0.01)
        await mw({}, handler)

        with pytest.raises(MiddlewareRateLimitError):
            await mw({}, handler)

        await asyncio.sleep(0.02)  # Wait for refill

        result = await mw({}, handler)
        assert result == "ok"


class TestConcurrencyLocks:
    @pytest.mark.asyncio
    async def test_rate_limiter_has_asyncio_lock(self) -> None:
        """P0-4: RateLimiterMiddleware must have asyncio.Lock."""
        rl = RateLimiterMiddleware(max_requests=10, window_seconds=60.0)
        assert hasattr(rl, "_lock")
        assert isinstance(rl._lock, asyncio.Lock)

    @pytest.mark.asyncio
    async def test_circuit_breaker_middleware_has_asyncio_lock(self) -> None:
        """P1-6: CircuitBreakerMiddleware must have asyncio.Lock."""
        cb = CircuitBreakerMiddleware(failure_threshold=3, recovery_timeout=30.0)
        assert hasattr(cb, "_lock")
        assert isinstance(cb._lock, asyncio.Lock)


class TestConditionalMiddleware:
    @pytest.mark.asyncio
    async def test_applies_when_predicate_true(self) -> None:
        from quadkit.middleware.builtins import TimingMiddleware

        inner = TimingMiddleware()
        mw = ConditionalMiddleware(inner, predicate=lambda ctx: True)
        result = await mw({"path": "/api"}, passthrough)
        assert result is not None

    @pytest.mark.asyncio
    async def test_skips_when_predicate_false(self) -> None:
        calls: list[str] = []

        async def tracking_mw(ctx: Any, next_handler: Any) -> Any:
            calls.append("tracked")
            return await next_handler(ctx)

        mw = ConditionalMiddleware(tracking_mw, predicate=lambda ctx: False)

        async def handler(ctx: Any) -> str:
            return "done"

        result = await mw({}, handler)
        assert result == "done"
        assert calls == []  # Inner middleware was NOT called

    @pytest.mark.asyncio
    async def test_applies_based_on_context(self) -> None:
        calls: list[str] = []

        async def tracking_mw(ctx: Any, next_handler: Any) -> Any:
            calls.append("tracked")
            return await next_handler(ctx)

        mw = ConditionalMiddleware(
            tracking_mw,
            predicate=lambda ctx: ctx.get("needs_tracking", False),
        )

        async def handler(ctx: Any) -> str:
            return "done"

        await mw({"needs_tracking": True}, handler)
        assert calls == ["tracked"]

        await mw({"needs_tracking": False}, handler)
        assert calls == ["tracked"]  # Still only one call
