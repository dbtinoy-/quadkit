"""Tests for HTTP interceptor pipeline and built-in interceptors."""
from __future__ import annotations

import time
from typing import Any
from unittest.mock import MagicMock

import pytest

from quadkit.web.interceptors.pipeline import (
    DefaultCallHandler,
    InterceptorChain,
    InterceptorPipeline,
)
from quadkit.web.interceptors.builtin.cache import CacheInterceptor
from quadkit.web.interceptors.builtin.logging import LoggingInterceptor


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _MockContext:
    """Minimal ExecutionContextProtocol implementation for testing."""

    def __init__(self, method: str = "GET", path: str = "/") -> None:
        self._method = method
        self._path = path
        self.request = _MockRequest(method, path)

    @property
    def handler(self):
        return None

    @property
    def controller_class(self):
        return None

    @property
    def method_name(self):
        return None

    @property
    def route_metadata(self):
        return {}


class _MockRequest:
    def __init__(self, method: str = "GET", path: str = "/") -> None:
        self.method = method

        class _URL:
            pass

        url = _URL()
        url.path = path  # type: ignore[attr-defined]
        self.url = url
        self.query_params = {}
        self.headers = {}


class _MockResponse:
    """Minimal response-like object."""

    def __init__(self, status_code: int = 200) -> None:
        self.status_code = status_code
        self.headers: dict[str, str] = {}


class _RecordingInterceptor:
    """Interceptor that records calls and forwards to next handler."""

    def __init__(self) -> None:
        self.call_count = 0

    async def intercept(self, context, next_handler) -> Any:
        self.call_count += 1
        return await next_handler.handle()


class _OverridingInterceptor:
    """Interceptor that returns a constant without calling next."""

    def __init__(self, result: Any) -> None:
        self._result = result

    async def intercept(self, context, next_handler) -> Any:
        return self._result


# ---------------------------------------------------------------------------
# DefaultCallHandler
# ---------------------------------------------------------------------------


class TestDefaultCallHandler:
    @pytest.mark.asyncio
    async def test_calls_handler(self) -> None:
        async def handler():
            return "result"

        dch = DefaultCallHandler(handler)
        result = await dch.handle()
        assert result == "result"

    @pytest.mark.asyncio
    async def test_handler_exception_propagates(self) -> None:
        async def bad_handler():
            raise ValueError("oops")

        dch = DefaultCallHandler(bad_handler)
        with pytest.raises(ValueError, match="oops"):
            await dch.handle()


# ---------------------------------------------------------------------------
# InterceptorPipeline
# ---------------------------------------------------------------------------


class TestInterceptorPipeline:
    @pytest.mark.asyncio
    async def test_empty_pipeline_calls_handler(self) -> None:
        pipeline = InterceptorPipeline()
        context = _MockContext()

        async def handler():
            return "direct"

        result = await pipeline.execute(context, handler)
        assert result == "direct"

    @pytest.mark.asyncio
    async def test_single_interceptor_called(self) -> None:
        recorder = _RecordingInterceptor()
        pipeline = InterceptorPipeline([recorder])
        context = _MockContext()

        async def handler():
            return "ok"

        await pipeline.execute(context, handler)
        assert recorder.call_count == 1

    @pytest.mark.asyncio
    async def test_two_interceptors_both_fired(self) -> None:
        r1 = _RecordingInterceptor()
        r2 = _RecordingInterceptor()
        pipeline = InterceptorPipeline([r1, r2])
        context = _MockContext()

        async def handler():
            return "ok"

        await pipeline.execute(context, handler)
        assert r1.call_count == 1
        assert r2.call_count == 1

    @pytest.mark.asyncio
    async def test_overriding_interceptor_short_circuits(self) -> None:
        override = _OverridingInterceptor("overridden")
        recorder = _RecordingInterceptor()
        pipeline = InterceptorPipeline([override, recorder])
        context = _MockContext()

        async def handler():
            return "should_not_reach"

        result = await pipeline.execute(context, handler)
        assert result == "overridden"
        assert recorder.call_count == 0

    def test_add_interceptor(self) -> None:
        pipeline = InterceptorPipeline()
        r = _RecordingInterceptor()
        pipeline.add_interceptor(r)
        assert r in pipeline.interceptors

    def test_duplicate_interceptor_not_added_twice(self) -> None:
        pipeline = InterceptorPipeline()
        r = _RecordingInterceptor()
        pipeline.add_interceptor(r)
        pipeline.add_interceptor(r)
        assert len(pipeline) == 1

    def test_remove_interceptor(self) -> None:
        r = _RecordingInterceptor()
        pipeline = InterceptorPipeline([r])
        pipeline.remove_interceptor(r)
        assert len(pipeline) == 0

    def test_clear_removes_all(self) -> None:
        pipeline = InterceptorPipeline(
            [_RecordingInterceptor(), _RecordingInterceptor()]
        )
        pipeline.clear()
        assert len(pipeline) == 0

    def test_bool_false_when_empty(self) -> None:
        assert not InterceptorPipeline()

    def test_bool_true_when_has_interceptors(self) -> None:
        assert InterceptorPipeline([_RecordingInterceptor()])


# ---------------------------------------------------------------------------
# CacheInterceptor
# ---------------------------------------------------------------------------


class TestCacheInterceptor:
    @pytest.mark.asyncio
    async def test_non_get_bypasses_cache(self) -> None:
        cache_interceptor = CacheInterceptor()
        context = _MockContext(method="POST")
        call_count = [0]

        async def handler():
            call_count[0] += 1
            return _MockResponse()

        pipeline = InterceptorPipeline([cache_interceptor])
        await pipeline.execute(context, handler)
        await pipeline.execute(context, handler)
        assert call_count[0] == 2  # not cached

    @pytest.mark.asyncio
    async def test_get_cached_on_second_call(self) -> None:
        cache_interceptor = CacheInterceptor(ttl=60)
        context = _MockContext(method="GET", path="/items")
        call_count = [0]

        async def handler():
            call_count[0] += 1
            return _MockResponse(status_code=200)

        pipeline = InterceptorPipeline([cache_interceptor])
        r1 = await pipeline.execute(context, handler)
        r2 = await pipeline.execute(context, handler)
        assert call_count[0] == 1  # second call from cache
        assert r1 is r2

    @pytest.mark.asyncio
    async def test_cache_miss_header_on_first_call(self) -> None:
        cache_interceptor = CacheInterceptor(ttl=60)
        context = _MockContext(method="GET")

        async def handler():
            return _MockResponse()

        pipeline = InterceptorPipeline([cache_interceptor])
        result = await pipeline.execute(context, handler)
        assert result.headers.get("X-Cache") == "MISS"

    @pytest.mark.asyncio
    async def test_cache_hit_header_on_second_call(self) -> None:
        cache_interceptor = CacheInterceptor(ttl=60)
        context = _MockContext(method="GET")

        async def handler():
            return _MockResponse()

        pipeline = InterceptorPipeline([cache_interceptor])
        await pipeline.execute(context, handler)
        result = await pipeline.execute(context, handler)
        assert result.headers.get("X-Cache") == "HIT"

    @pytest.mark.asyncio
    async def test_non_200_response_not_cached(self) -> None:
        cache_interceptor = CacheInterceptor(ttl=60)
        context = _MockContext(method="GET")
        call_count = [0]

        async def handler():
            call_count[0] += 1
            return _MockResponse(status_code=404)

        pipeline = InterceptorPipeline([cache_interceptor])
        await pipeline.execute(context, handler)
        await pipeline.execute(context, handler)
        assert call_count[0] == 2  # 404s not cached

    def test_clear_cache(self) -> None:
        ci = CacheInterceptor()
        ci._cache["key"] = ("value", time.time() + 9999)
        ci.clear_cache()
        assert ci._cache == {}

    def test_custom_cache_key_builder(self) -> None:
        called = [False]

        def custom_key(request):
            called[0] = True
            return "fixed_key"

        ci = CacheInterceptor(cache_key_builder=custom_key)
        # simply check the builder is stored
        assert ci._cache_key_builder is custom_key


# ---------------------------------------------------------------------------
# LoggingInterceptor
# ---------------------------------------------------------------------------


class TestLoggingInterceptor:
    @pytest.mark.asyncio
    async def test_forwards_result(self) -> None:
        interceptor = LoggingInterceptor()
        context = _MockContext(method="GET", path="/users")
        response = _MockResponse(status_code=200)

        async def handler():
            return response

        pipeline = InterceptorPipeline([interceptor])
        result = await pipeline.execute(context, handler)
        assert result is response

    @pytest.mark.asyncio
    async def test_custom_logger_name_accepted(self) -> None:
        interceptor = LoggingInterceptor(logger_name="test.logger")
        assert interceptor is not None

    @pytest.mark.asyncio
    async def test_log_request_false_still_works(self) -> None:
        interceptor = LoggingInterceptor(log_request=False, log_response=False)
        context = _MockContext()

        async def handler():
            return _MockResponse()

        pipeline = InterceptorPipeline([interceptor])
        result = await pipeline.execute(context, handler)
        assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_exception_propagates(self) -> None:
        interceptor = LoggingInterceptor()
        context = _MockContext()

        async def handler():
            raise ValueError("handler failure")

        pipeline = InterceptorPipeline([interceptor])
        with pytest.raises(ValueError, match="handler failure"):
            await pipeline.execute(context, handler)
