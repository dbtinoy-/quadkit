"""Tests for middleware enhancements — registry, common, pipeline."""

from __future__ import annotations

from typing import Any

import pytest

from quadkit.app.pipeline import MiddlewarePipeline
from quadkit.middleware.builtins import (
    ErrorHandlerMiddleware,
    LoggingMiddleware,
    TimingMiddleware,
)
from quadkit.middleware.core.registry import MiddlewareRegistry

# ---------------------------------------------------------------------------
# MiddlewareRegistry
# ---------------------------------------------------------------------------


class TestMiddlewareRegistry:
    """Tests for MiddlewareRegistry."""

    def test_register_and_get(self) -> None:
        reg = MiddlewareRegistry()
        mw = TimingMiddleware()
        reg.register("timing", mw)
        assert reg.get("timing") is mw

    def test_get_missing_raises(self) -> None:
        reg = MiddlewareRegistry()
        with pytest.raises(KeyError):
            reg.get("missing")

    def test_has(self) -> None:
        reg = MiddlewareRegistry()
        assert not reg.has("timing")
        reg.register("timing", TimingMiddleware())
        assert reg.has("timing")

    def test_names(self) -> None:
        reg = MiddlewareRegistry()
        reg.register("a", TimingMiddleware())
        reg.register("b", LoggingMiddleware())
        assert set(reg.names()) == {"a", "b"}

    def test_unregister(self) -> None:
        reg = MiddlewareRegistry()
        mw = TimingMiddleware()
        reg.register("x", mw)
        removed = reg.unregister("x")
        assert removed is mw
        assert not reg.has("x")

    def test_unregister_missing_raises(self) -> None:
        reg = MiddlewareRegistry()
        with pytest.raises(KeyError):
            reg.unregister("missing")

    def test_priority_ordering(self) -> None:
        reg = MiddlewareRegistry()
        mw_low = TimingMiddleware()
        mw_high = LoggingMiddleware()
        reg.register("high", mw_high, priority=10)
        reg.register("low", mw_low, priority=100)
        all_mw = reg.all()
        assert all_mw[0] is mw_high
        assert all_mw[1] is mw_low

    def test_register_duplicate_raises(self) -> None:
        reg = MiddlewareRegistry()
        reg.register("a", TimingMiddleware())
        with pytest.raises(ValueError):
            reg.register("a", TimingMiddleware())

    def test_len_and_contains(self) -> None:
        reg = MiddlewareRegistry()
        assert len(reg) == 0
        reg.register("a", TimingMiddleware())
        assert len(reg) == 1
        assert "a" in reg


# ---------------------------------------------------------------------------
# TimingMiddleware
# ---------------------------------------------------------------------------


class TestTimingMiddleware:
    """Tests for TimingMiddleware."""

    @pytest.mark.asyncio
    async def test_timing_middleware(self) -> None:
        mw = TimingMiddleware()
        ctx: dict[str, Any] = {}

        async def handler(context: Any) -> str:
            return "done"

        result = await mw(ctx, handler)
        assert result == "done"


# ---------------------------------------------------------------------------
# LoggingMiddleware
# ---------------------------------------------------------------------------


class TestLoggingMiddleware:
    """Tests for LoggingMiddleware."""

    @pytest.mark.asyncio
    async def test_logging_middleware(self) -> None:
        mw = LoggingMiddleware()
        ctx: dict[str, Any] = {"func": lambda: None}

        async def handler(context: Any) -> str:
            return "ok"

        result = await mw(ctx, handler)
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_logging_middleware_on_error(self) -> None:
        mw = LoggingMiddleware()
        ctx: dict[str, Any] = {"func": lambda: None}

        async def bad_handler(context: Any) -> str:
            raise ValueError("boom")

        with pytest.raises(ValueError, match="boom"):
            await mw(ctx, bad_handler)


# ---------------------------------------------------------------------------
# ErrorHandlerMiddleware
# ---------------------------------------------------------------------------


class TestErrorHandlerMiddleware:
    """Tests for ErrorHandlerMiddleware."""

    @pytest.mark.asyncio
    async def test_error_handler_returns_fallback(self) -> None:
        mw = ErrorHandlerMiddleware(catch=RuntimeError, fallback="fallback_value")
        ctx: dict[str, Any] = {}

        async def bad_handler(context: Any) -> str:
            raise RuntimeError("fail")

        result = await mw(ctx, bad_handler)
        assert result == "fallback_value"

    @pytest.mark.asyncio
    async def test_error_handler_calls_custom_handler(self) -> None:
        errors: list[Exception] = []

        def capture_error(exc: Exception, context: Any) -> str:
            errors.append(exc)
            return "recovered"

        mw = ErrorHandlerMiddleware(catch=RuntimeError, error_handler=capture_error)
        ctx: dict[str, Any] = {}

        async def bad_handler(context: Any) -> str:
            raise RuntimeError("fail")

        result = await mw(ctx, bad_handler)
        assert result == "recovered"
        assert len(errors) == 1

    @pytest.mark.asyncio
    async def test_success_passes_through(self) -> None:
        mw = ErrorHandlerMiddleware(catch=Exception, fallback="nope")
        ctx: dict[str, Any] = {}

        async def good_handler(context: Any) -> str:
            return "success"

        result = await mw(ctx, good_handler)
        assert result == "success"


# ---------------------------------------------------------------------------
# MiddlewarePipeline
# ---------------------------------------------------------------------------


class TestMiddlewarePipeline:
    """Tests for MiddlewarePipeline."""

    @pytest.mark.asyncio
    async def test_empty_pipeline(self) -> None:
        pipeline = MiddlewarePipeline()
        ctx: dict[str, Any] = {}

        async def handler(context: Any) -> str:
            return "raw"

        result = await pipeline.execute(ctx, handler)
        assert result == "raw"

    @pytest.mark.asyncio
    async def test_single_middleware(self) -> None:
        pipeline = MiddlewarePipeline().add(TimingMiddleware())
        ctx: dict[str, Any] = {}

        async def handler(context: Any) -> str:
            return "timed"

        result = await pipeline.execute(ctx, handler)
        assert result == "timed"

    @pytest.mark.asyncio
    async def test_immutability(self) -> None:
        p1 = MiddlewarePipeline()
        p2 = p1.add(TimingMiddleware())
        assert len(p1) == 0
        assert len(p2) == 1

    @pytest.mark.asyncio
    async def test_chained_middleware(self) -> None:
        call_order: list[str] = []

        class TrackingMiddleware:
            def __init__(self, name: str) -> None:
                self._name = name

            async def __call__(self, ctx: dict, next_handler: Any) -> Any:
                call_order.append(f"before:{self._name}")
                result = await next_handler(ctx)
                call_order.append(f"after:{self._name}")
                return result

        pipeline = (
            MiddlewarePipeline()
            .add(TrackingMiddleware("first"))
            .add(TrackingMiddleware("second"))
        )
        ctx: dict[str, Any] = {}

        async def handler(context: Any) -> str:
            call_order.append("handler")
            return "done"

        await pipeline.execute(ctx, handler)
        assert call_order == [
            "before:first",
            "before:second",
            "handler",
            "after:second",
            "after:first",
        ]
