from dataclasses import dataclass
import inspect
from unittest.mock import AsyncMock, MagicMock

import pytest
from starlette.requests import Request

from quadkit.domain import DomainModel
from quadkit.web.routing.execution_context import WebExecutionContext
from quadkit.web.routing.parameter_binder import ParameterBinder


@dataclass
class UserUpdate(DomainModel):
    name: str
    age: int


class TestParameterBinder:
    @pytest.fixture
    def mock_request(self):
        req = MagicMock(spec=Request)
        req.state = MagicMock()
        req.query_params = {}
        req.path_params = {}
        return req

    @pytest.mark.asyncio
    async def test_bind_path_params(self, mock_request):
        def handler(user_id: int):
            return user_id

        mock_request.path_params = {"user_id": 123}
        sig = inspect.signature(handler)

        context = WebExecutionContext(
            request=mock_request,
            handler=handler,
            route_metadata={"sig_info": {"sig": sig, "hints": {"user_id": int}}},
        )

        binder = ParameterBinder(sig, {"user_id": int})
        kwargs = await binder.bind(context)

        assert kwargs["user_id"] == 123

    @pytest.mark.asyncio
    async def test_bind_query_params(self, mock_request):
        def handler(q: str = "default"):
            return q

        mock_request.query_params = {"q": "search"}
        sig = inspect.signature(handler)

        context = WebExecutionContext(
            request=mock_request,
            handler=handler,
            route_metadata={"sig_info": {"sig": sig, "hints": {"q": str}}},
        )

        binder = ParameterBinder(sig, {"q": str})
        kwargs = await binder.bind(context)

        assert kwargs["q"] == "search"

    @pytest.mark.asyncio
    async def test_bind_di_service(self, mock_request):
        class MyService:
            pass

        def handler(svc: MyService):
            return svc

        service_instance = MyService()
        container = MagicMock()
        container.resolve = AsyncMock(return_value=service_instance)

        sig = inspect.signature(handler)
        context = WebExecutionContext(
            request=mock_request,
            handler=handler,
            container=container,
            route_metadata={"sig_info": {"sig": sig, "hints": {"svc": MyService}}},
        )

        binder = ParameterBinder(sig, {"svc": MyService})
        kwargs = await binder.bind(context)

        assert kwargs["svc"] is service_instance
        container.resolve.assert_awaited_once_with(MyService)

    @pytest.mark.asyncio
    async def test_bind_pydantic_model(self, mock_request):
        def handler(data: UserUpdate):
            return data

        mock_request.json = AsyncMock(return_value={"name": "Alice", "age": 30})

        sig = inspect.signature(handler)
        context = WebExecutionContext(
            request=mock_request,
            handler=handler,
            route_metadata={"sig_info": {"sig": sig, "hints": {"data": UserUpdate}}},
        )

        binder = ParameterBinder(sig, {"data": UserUpdate})
        kwargs = await binder.bind(context)

        assert isinstance(kwargs["data"], UserUpdate)
        assert kwargs["data"].name == "Alice"
        assert kwargs["data"].age == 30


class TestZeroParamFastPath:
    """plans/09172026 R-05 — request/context-only handlers skip binding.

    When every handler parameter (besides ``self``) is a request or
    execution-context injection, the request pipeline must call the handler
    directly: no ``ParameterBinder`` construction, no ``bind()``, no
    ``validate_and_merge_request`` pass. Any other signature keeps the full
    binder path.
    """

    @staticmethod
    def _make_app():
        import asyncio

        from starlette.requests import Request

        from quadkit.di.container import Container
        from quadkit.web import Controller, get
        from quadkit.web.config import RateLimitConfig, WebConfig
        from quadkit.web.di.provider import WebProvider

        class FastPathController(Controller):
            @get("/fp-zero")
            async def zero(self) -> dict:
                return {"ok": True}

            @get("/fp-request")
            async def with_request(self, request: Request) -> dict:
                return {"request_id": request.state.request_id}

            @get("/fp-query")
            async def with_query(self, value: int = 1) -> dict:
                return {"value": value}

        provider = WebProvider(
            controllers=[FastPathController],
            web_config=WebConfig(rate_limit=RateLimitConfig(enabled=False)),
        )
        container = Container()
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(provider.register(container))
            loop.run_until_complete(provider.boot(container))
        finally:
            loop.close()
        return provider

    def test_request_only_handlers_skip_binder(self, monkeypatch) -> None:
        provider = self._make_app()

        import quadkit.web.routing.parameter_binder as binder_module

        calls = {"bind": 0}
        orig_bind = binder_module.ParameterBinder.bind

        async def counting_bind(self, context):
            calls["bind"] += 1
            return await orig_bind(self, context)

        monkeypatch.setattr(binder_module.ParameterBinder, "bind", counting_bind)

        from starlette.testclient import TestClient

        client = TestClient(provider.starlette)

        zero = client.get("/fp-zero")
        request_route = client.get("/fp-request")

        assert zero.status_code == 200
        assert zero.json() == {"ok": True}
        assert request_route.status_code == 200
        # The request param was bound by the fast path itself.
        assert (
            request_route.json()["request_id"] == request_route.headers["x-request-id"]
        )
        # Neither route entered ParameterBinder.bind.
        assert calls["bind"] == 0

    def test_other_signatures_keep_full_binding(self, monkeypatch) -> None:
        provider = self._make_app()

        import quadkit.web.routing.parameter_binder as binder_module

        calls = {"bind": 0}
        orig_bind = binder_module.ParameterBinder.bind

        async def counting_bind(self, context):
            calls["bind"] += 1
            return await orig_bind(self, context)

        monkeypatch.setattr(binder_module.ParameterBinder, "bind", counting_bind)

        from starlette.testclient import TestClient

        client = TestClient(provider.starlette)

        response = client.get("/fp-query", params={"value": 7})

        assert response.status_code == 200
        assert response.json() == {"value": 7}
        assert calls["bind"] == 1

    def test_simple_binding_plan_computation(self) -> None:
        """The router's wrap-time plan classifies signatures correctly."""
        from starlette.requests import Request

        from quadkit.web import Controller, get
        from quadkit.web.routing.router import Router

        class PlanController(Controller):
            @get("/a")
            async def zero(self) -> dict:
                return {}

            @get("/b")
            async def req_only(self, request: Request) -> dict:
                return {}

            @get("/c")
            async def query(self, value: int = 1) -> dict:
                return {"value": value}

        router = Router()

        assert router._compute_simple_binding(PlanController, "zero") == {}
        assert router._compute_simple_binding(PlanController, "req_only") == {
            "request": "request"
        }
        assert router._compute_simple_binding(PlanController, "query") is None
