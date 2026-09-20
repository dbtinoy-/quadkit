"""Tests for multiple small modules to push coverage over 80%.

Covers:
- background/decorator.py
- server/lifecycle.py  
- docs/decorators.py
- sse/decorators.py
- middleware/tracing.py
- interceptors/builtin/transform.py
- middleware/body_limit.py
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from starlette.responses import PlainTextResponse
from starlette.testclient import TestClient


# ─── background/decorator.py ───────────────────────────────────────────────

class TestBackgroundDecorator:
    @pytest.mark.asyncio
    async def test_wraps_async_function(self) -> None:
        from quadkit.web.background.decorator import background

        called = []

        @background
        async def my_task(x: int) -> str:
            called.append(x)
            return "done"

        await my_task(42)
        assert called == [42]

    @pytest.mark.asyncio
    async def test_wraps_sync_function(self) -> None:
        from quadkit.web.background.decorator import background

        called = []

        @background
        def sync_task(x: int) -> None:
            called.append(x)

        await sync_task(99)
        assert called == [99]

    def test_returns_callable(self) -> None:
        from quadkit.web.background.decorator import background

        @background
        async def task() -> None: ...

        assert callable(task)


# ─── server/lifecycle.py ────────────────────────────────────────────────────

class TestServerLifecycle:
    def test_init_stores_config(self) -> None:
        from quadkit.web.server.lifecycle import ServerLifecycle
        from quadkit.web.config import ServerConfig

        cfg = ServerConfig()
        lc = ServerLifecycle(cfg)
        assert lc.config is cfg
        assert lc.server is None

    @pytest.mark.asyncio
    async def test_start_is_noop(self) -> None:
        from quadkit.web.server.lifecycle import ServerLifecycle
        from quadkit.web.config import ServerConfig

        lc = ServerLifecycle(ServerConfig())
        await lc.start()  # Should not raise

    @pytest.mark.asyncio
    async def test_stop_when_server_is_none(self) -> None:
        from quadkit.web.server.lifecycle import ServerLifecycle
        from quadkit.web.config import ServerConfig

        lc = ServerLifecycle(ServerConfig())
        await lc.stop()  # Should not raise (server is None)

    @pytest.mark.asyncio
    async def test_stop_closes_server(self) -> None:
        from quadkit.web.server.lifecycle import ServerLifecycle
        from quadkit.web.config import ServerConfig

        lc = ServerLifecycle(ServerConfig())
        mock_server = MagicMock()
        mock_server.wait_closed = AsyncMock()
        lc.server = mock_server

        await lc.stop()
        mock_server.close.assert_called_once()
        mock_server.wait_closed.assert_awaited_once()


# ─── docs/decorators.py ─────────────────────────────────────────────────────

class TestOpenApiDecorator:
    def test_sets_route_config_on_function(self) -> None:
        from quadkit.web.docs.decorators import openapi

        @openapi(summary="Get users", tags=["users"])
        def get_users(): ...

        assert get_users._route_config["summary"] == "Get users"
        assert get_users._route_config["tags"] == ["users"]

    def test_initializes_route_config_if_missing(self) -> None:
        from quadkit.web.docs.decorators import openapi

        def handler(): ...

        openapi(description="desc")(handler)
        assert handler._route_config["description"] == "desc"

    def test_merges_with_existing_route_config(self) -> None:
        from quadkit.web.docs.decorators import openapi

        def handler(): ...
        handler._route_config = {"existing_key": "val"}

        openapi(summary="new")(handler)
        assert handler._route_config["existing_key"] == "val"
        assert handler._route_config["summary"] == "new"

    def test_sets_deprecated_flag(self) -> None:
        from quadkit.web.docs.decorators import openapi

        @openapi(deprecated=True)
        def old_endpoint(): ...

        assert old_endpoint._route_config["deprecated"] is True

    def test_returns_same_function(self) -> None:
        from quadkit.web.docs.decorators import openapi

        def handler(): ...
        result = openapi(summary="x")(handler)
        assert result is handler

    def test_extra_kwargs_forwarded(self) -> None:
        from quadkit.web.docs.decorators import openapi

        @openapi(x_custom="value")
        def handler(): ...

        assert handler._route_config["x_custom"] == "value"


# ─── sse/decorators.py ───────────────────────────────────────────────────────

class TestSseEndpointDecorator:
    def test_sets_sse_path_attribute(self) -> None:
        from quadkit.web.sse.decorators import sse_endpoint

        @sse_endpoint("/events")
        class MyHandler:
            pass

        assert MyHandler._sse_path == "/events"

    def test_marks_as_sse_handler(self) -> None:
        from quadkit.web.sse.decorators import sse_endpoint

        @sse_endpoint("/stream")
        class MyHandler:
            pass

        assert MyHandler._is_sse_handler is True

    def test_sets_metadata(self) -> None:
        from quadkit.web.sse.decorators import sse_endpoint

        @sse_endpoint("/stream", heartbeat_interval=15, retry=3000)
        class MyHandler:
            pass

        meta = MyHandler._sse_metadata
        assert meta["path"] == "/stream"
        assert meta["heartbeat_interval"] == 15
        assert meta["retry"] == 3000

    def test_overrides_heartbeat_interval_on_class(self) -> None:
        from quadkit.web.sse.decorators import sse_endpoint

        @sse_endpoint("/stream", heartbeat_interval=20)
        class MyHandler:
            heartbeat_interval = 30

        assert MyHandler.heartbeat_interval == 20

    def test_overrides_retry_on_class(self) -> None:
        from quadkit.web.sse.decorators import sse_endpoint

        @sse_endpoint("/stream", retry=5000)
        class MyHandler:
            retry = 1000

        assert MyHandler.retry == 5000

    def test_no_optional_params(self) -> None:
        from quadkit.web.sse.decorators import sse_endpoint

        @sse_endpoint("/feed")
        class MyHandler:
            pass

        assert MyHandler._sse_metadata["heartbeat_interval"] is None
        assert MyHandler._sse_metadata["retry"] is None

    def test_returns_same_class(self) -> None:
        from quadkit.web.sse.decorators import sse_endpoint

        class MyHandler:
            pass

        result = sse_endpoint("/x")(MyHandler)
        assert result is MyHandler


# ─── middleware/tracing.py ──────────────────────────────────────────────────

class TestTraceparentUtils:
    def test_extract_valid_traceparent(self) -> None:
        from quadkit.web.middleware.tracing import extract_traceparent

        header = "00-" + "a" * 32 + "-" + "b" * 16 + "-01"
        result = extract_traceparent(header)
        assert result is not None
        assert result["trace_id"] == "a" * 32
        assert result["parent_id"] == "b" * 16
        assert result["trace_flags"] == "01"

    def test_extract_invalid_traceparent_returns_none(self) -> None:
        from quadkit.web.middleware.tracing import extract_traceparent

        assert extract_traceparent("invalid") is None
        assert extract_traceparent("") is None

    def test_extract_trims_whitespace(self) -> None:
        from quadkit.web.middleware.tracing import extract_traceparent

        header = "  00-" + "a" * 32 + "-" + "b" * 16 + "-01  "
        result = extract_traceparent(header)
        assert result is not None

    def test_inject_traceparent_returns_none_when_no_context(self) -> None:
        from quadkit.web.middleware.tracing import inject_traceparent
        from quadkit.contracts.core.trace_context import trace_id_var, span_id_var

        # Reset context vars
        t = trace_id_var.set(None)
        s = span_id_var.set(None)
        try:
            result = inject_traceparent()
            assert result is None
        finally:
            trace_id_var.reset(t)
            span_id_var.reset(s)

    def test_inject_traceparent_with_context(self) -> None:
        from quadkit.web.middleware.tracing import inject_traceparent
        from quadkit.contracts.core.trace_context import trace_id_var, span_id_var

        t = trace_id_var.set("a" * 32)
        s = span_id_var.set("b" * 16)
        try:
            result = inject_traceparent()
            assert result is not None
            assert "a" * 32 in result
            assert "b" * 16 in result
        finally:
            trace_id_var.reset(t)
            span_id_var.reset(s)

    def test_load_trace_to_context_no_header(self) -> None:
        from quadkit.web.middleware.tracing import load_trace_to_context

        ctx = MagicMock()
        load_trace_to_context(ctx, None)  # Should not raise
        ctx.assert_not_called()

    def test_load_trace_to_context_valid_header(self) -> None:
        from quadkit.web.middleware.tracing import load_trace_to_context

        header = "00-" + "a" * 32 + "-" + "b" * 16 + "-01"
        ctx = MagicMock()
        load_trace_to_context(ctx, header)
        assert ctx.trace_id == "a" * 32
        assert ctx.trace_flags == "01"

    def test_load_trace_to_context_invalid_header(self) -> None:
        from quadkit.web.middleware.tracing import load_trace_to_context

        ctx = MagicMock()
        load_trace_to_context(ctx, "garbage")  # Should not raise or set attrs


# ─── interceptors/builtin/transform.py ─────────────────────────────────────

class TestTransformInterceptor:
    @pytest.mark.asyncio
    async def test_passthrough_without_transform(self) -> None:
        from quadkit.web.interceptors.builtin.transform import TransformInterceptor

        interceptor = TransformInterceptor()
        ctx = MagicMock()
        handler = MagicMock()
        handler.handle = AsyncMock(return_value={"data": "value"})

        result = await interceptor.intercept(ctx, handler)
        assert result == {"data": "value"}

    @pytest.mark.asyncio
    async def test_applies_custom_transform(self) -> None:
        from quadkit.web.interceptors.builtin.transform import TransformInterceptor

        interceptor = TransformInterceptor(transform=lambda x: {"wrapped": x})
        ctx = MagicMock()
        handler = MagicMock()
        handler.handle = AsyncMock(return_value="original")

        result = await interceptor.intercept(ctx, handler)
        assert result == {"wrapped": "original"}

    @pytest.mark.asyncio
    async def test_wrap_response_flag(self) -> None:
        from quadkit.web.interceptors.builtin.transform import TransformInterceptor

        interceptor = TransformInterceptor(wrap_response=True)
        ctx = MagicMock()
        handler = MagicMock()
        handler.handle = AsyncMock(return_value={"key": "val"})

        result = await interceptor.intercept(ctx, handler)
        assert result == {"success": True, "data": {"key": "val"}}

    def test_transform_method_identity(self) -> None:
        from quadkit.web.interceptors.builtin.transform import TransformInterceptor

        interceptor = TransformInterceptor()
        data = {"key": "val"}
        assert interceptor.transform(data) is data

    def test_wrap_method(self) -> None:
        from quadkit.web.interceptors.builtin.transform import TransformInterceptor

        interceptor = TransformInterceptor()
        wrapped = interceptor._wrap("payload")
        assert wrapped == {"success": True, "data": "payload"}


# ─── middleware/body_limit.py ───────────────────────────────────────────────

async def _plain_inner(scope, receive, send) -> None:
    response = PlainTextResponse("ok")
    await response(scope, receive, send)


class TestRequestBodySizeLimitMiddleware:
    def test_allows_small_body(self) -> None:
        from quadkit.web.middleware.body_limit import RequestBodySizeLimitMiddleware

        mw = RequestBodySizeLimitMiddleware(_plain_inner, max_body_size=1024)
        client = TestClient(mw)
        response = client.post(
            "/data",
            content=b"small body",
            headers={"content-length": "10"},
        )
        assert response.status_code == 200

    def test_rejects_oversized_body(self) -> None:
        from quadkit.web.middleware.body_limit import RequestBodySizeLimitMiddleware

        mw = RequestBodySizeLimitMiddleware(_plain_inner, max_body_size=5)
        client = TestClient(mw)
        response = client.post(
            "/data",
            content=b"this is more than 5 bytes",
            headers={"content-length": "25"},
        )
        assert response.status_code == 413

    def test_no_content_length_passes_through(self) -> None:
        from quadkit.web.middleware.body_limit import RequestBodySizeLimitMiddleware

        mw = RequestBodySizeLimitMiddleware(_plain_inner, max_body_size=1)
        client = TestClient(mw)
        # GET requests typically have no Content-Length
        response = client.get("/data")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_non_http_scope_passes_through(self) -> None:
        from quadkit.web.middleware.body_limit import RequestBodySizeLimitMiddleware

        called = []

        async def inner(scope, receive, send) -> None:
            called.append(scope["type"])

        mw = RequestBodySizeLimitMiddleware(inner)
        await mw({"type": "websocket"}, None, None)
        assert "websocket" in called

    def test_invalid_content_length_treats_as_zero(self) -> None:
        from quadkit.web.middleware.body_limit import RequestBodySizeLimitMiddleware

        mw = RequestBodySizeLimitMiddleware(_plain_inner, max_body_size=1)
        client = TestClient(mw)
        response = client.post(
            "/data",
            content=b"x",
            headers={"content-length": "not-a-number"},
        )
        # Invalid content-length treated as 0, so should pass through
        assert response.status_code == 200
