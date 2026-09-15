import inspect
from unittest.mock import AsyncMock, MagicMock

import pytest
from starlette.requests import Request

from quadkit.serialization import loads
from quadkit.web.routing.execution_context import WebExecutionContext
from quadkit.web.routing.pipeline import RequestPipeline


class TestRequestPipeline:
    @pytest.fixture
    def mock_request(self):
        req = MagicMock(spec=Request)
        req.state = MagicMock()
        req.query_params = {}
        req.path_params = {}
        return req

    @pytest.fixture
    def mock_handler(self):
        # Give the mock a real signature: inspect.signature() on a bare
        # AsyncMock is unreliable (its auto-generated __call__ confuses
        # inspect internals).
        async def _impl(*args, **kwargs):
            return {"status": "ok"}

        handler = AsyncMock(return_value={"status": "ok"})
        handler.__signature__ = inspect.signature(_impl)
        handler.__globals__ = {}
        return handler

    @pytest.fixture
    def context(self, mock_request, mock_handler):
        sig = inspect.signature(mock_handler)
        return WebExecutionContext(
            request=mock_request,
            handler=mock_handler,
            route_metadata={"sig_info": {"sig": sig, "hints": {}}},
        )

    @pytest.mark.asyncio
    async def test_pipeline_executes_handler(self, context):
        pipeline = RequestPipeline()
        result = await pipeline.execute(context)
        assert result.status_code == 200
        assert loads(result.body) == {"status": "ok"}
        context.handler.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_guard_prevents_execution(self, context):
        guard = MagicMock()
        guard.can_activate = AsyncMock(return_value=False)
        
        pipeline = RequestPipeline(guards=[guard])
        
        from quadkit.web.exceptions import ForbiddenError
        with pytest.raises(ForbiddenError):
            await pipeline.execute(context)
            
        context.handler.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_interceptor_wraps_execution(self, context):
        class TraceInterceptor:
            async def intercept(self, ctx, next):
                ctx.set("before", True)
                res = await next.handle()
                res["after"] = True
                return res

        interceptor = TraceInterceptor()
        pipeline = RequestPipeline(interceptors=[interceptor])
        
        result = await pipeline.execute(context)
        
        assert result.status_code == 200
        assert loads(result.body) == {"status": "ok", "after": True}
        assert context.get("before") is True
        context.handler.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_multiple_interceptors_order(self, context):
        order = []
        
        class Interceptor:
            def __init__(self, name):
                self.name = name
            async def intercept(self, ctx, next):
                order.append(f"pre_{self.name}")
                res = await next.handle()
                order.append(f"post_{self.name}")
                return res

        pipeline = RequestPipeline(interceptors=[Interceptor("1"), Interceptor("2")])
        await pipeline.execute(context)
        
        assert order == ["pre_1", "pre_2", "post_2", "post_1"]

    @pytest.mark.asyncio
    async def test_pipeline_uses_injected_serializer_without_container_resolution(
        self,
        mock_request,
    ):
        async def _impl(*args, **kwargs):
            return {"ok": True}

        handler = AsyncMock(return_value={"ok": True})
        handler.__signature__ = inspect.signature(_impl)

        sig = inspect.signature(handler)

        container = MagicMock()
        container.resolve = AsyncMock(
            side_effect=AssertionError(
                "container.resolve must not be used for serializer dependencies",
            ),
        )

        context = WebExecutionContext(
            request=mock_request,
            handler=handler,
            route_metadata={"sig_info": {"sig": sig, "hints": {}}},
            container=container,
        )

        serializer = MagicMock()
        expected_response = MagicMock()
        serializer.serialize = AsyncMock(return_value=expected_response)

        pipeline = RequestPipeline(response_serializer=serializer)
        result = await pipeline.execute(context)

        assert result is expected_response
        serializer.serialize.assert_awaited_once()
        container.resolve.assert_not_called()
