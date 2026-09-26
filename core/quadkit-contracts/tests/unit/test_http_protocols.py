"""Tests for the web service-mesh protocols (registry, selectors, HTTP, WS)."""

from __future__ import annotations

from typing import Any

from quadkit.contracts.web.http_models import HttpResponse
from quadkit.contracts.web.http_protocols import (
    ConnectMetricsCollectorProtocol,
    HTTPClientProtocol,
    HTTPSessionProtocol,
    InterceptorChainProtocol,
    InterceptorProtocol,
    SelectorProtocol,
    ServiceInfo,
    ServiceMeshRegistryProtocol,
    WebSocketProtocol,
)


def _info(name: str = "svc", host: str = "h1", port: int = 8080) -> ServiceInfo:
    return ServiceInfo(name=name, host=host, port=port)


class _Registry:
    async def register(self, service: ServiceInfo) -> None: ...

    async def deregister(self, service_name: str, host: str, port: int) -> None: ...

    async def discover(self, service_name: str) -> list[ServiceInfo]: ...

    async def get_service(
        self, service_name: str, host: str, port: int
    ) -> ServiceInfo | None: ...

    async def list_services(self) -> list[str]: ...


class _Selector:
    async def select(self, instances: list[ServiceInfo]) -> ServiceInfo | None: ...


class _Session:
    async def request(self, method: str, url: str, **kwargs: Any) -> Any: ...

    async def close(self) -> None: ...


class _Client:
    async def start(self) -> None: ...

    async def stop(self) -> None: ...

    async def request(self, method: str, url: str, **kwargs: Any) -> HttpResponse: ...

    async def get(self, url: str, **kwargs: Any) -> HttpResponse: ...

    async def post(self, url: str, **kwargs: Any) -> HttpResponse: ...

    async def put(self, url: str, **kwargs: Any) -> HttpResponse: ...

    async def delete(self, url: str, **kwargs: Any) -> HttpResponse: ...

    async def patch(self, url: str, **kwargs: Any) -> HttpResponse: ...

    async def head(self, url: str, **kwargs: Any) -> HttpResponse: ...

    def stream_response(self, method: str, url: str, **kwargs: Any) -> Any: ...


class _Interceptor:
    async def intercept_request(self, context: Any) -> Any: ...

    async def intercept_response(self, response: Any) -> Any: ...


class _Chain:
    def add_interceptor(self, interceptor: InterceptorProtocol) -> None: ...

    def remove_interceptor(self, interceptor: InterceptorProtocol) -> None: ...

    async def process_request(self, context: Any) -> Any: ...

    async def process_response(self, response: Any) -> Any: ...


class _Metrics:
    def record_request(
        self, service: str, method: str, duration: float, status: int
    ) -> None: ...

    def get_metrics(self, service: str) -> dict[str, Any]: ...


class _WS:
    async def accept(self, subprotocol: str | None = None) -> None: ...

    async def receive_text(self) -> str: ...

    async def receive_json(self) -> Any: ...

    async def send_text(self, data: str) -> None: ...

    async def send_json(self, data: Any) -> None: ...

    async def close(self, code: int = 1000, reason: str = "") -> None: ...


class TestRuntimeCheckable:
    def test_registry_conformance(self) -> None:
        assert isinstance(_Registry(), ServiceMeshRegistryProtocol)

    def test_registry_missing_method_fails(self) -> None:
        class Incomplete:
            async def register(self, service: ServiceInfo) -> None: ...

        assert not isinstance(Incomplete(), ServiceMeshRegistryProtocol)

    def test_selector_conformance(self) -> None:
        assert isinstance(_Selector(), SelectorProtocol)

    def test_selector_needs_select(self) -> None:
        class Empty: ...

        assert not isinstance(Empty(), SelectorProtocol)

    def test_session_conformance(self) -> None:
        assert isinstance(_Session(), HTTPSessionProtocol)

    def test_client_conformance(self) -> None:
        assert isinstance(_Client(), HTTPClientProtocol)

    def test_client_missing_verb_fails(self) -> None:
        class NoHead(_Client):
            async def head(self, url: str, **kwargs: Any) -> HttpResponse: ...  # noqa: ARG002

        # head exists but renamed signature check: drop it instead
        class ClientSansPatch:
            async def start(self) -> None: ...

            async def stop(self) -> None: ...

            async def request(self, method: str, url: str, **kwargs: Any) -> HttpResponse: ...

            async def get(self, url: str, **kwargs: Any) -> HttpResponse: ...

            async def post(self, url: str, **kwargs: Any) -> HttpResponse: ...

            async def put(self, url: str, **kwargs: Any) -> HttpResponse: ...

            async def delete(self, url: str, **kwargs: Any) -> HttpResponse: ...

            async def head(self, url: str, **kwargs: Any) -> HttpResponse: ...

        assert not isinstance(ClientSansPatch(), HTTPClientProtocol)

    def test_interceptor_conformance(self) -> None:
        assert isinstance(_Interceptor(), InterceptorProtocol)

    def test_chain_conformance(self) -> None:
        assert isinstance(_Chain(), InterceptorChainProtocol)

    def test_metrics_conformance(self) -> None:
        assert isinstance(_Metrics(), ConnectMetricsCollectorProtocol)

    def test_websocket_conformance(self) -> None:
        assert isinstance(_WS(), WebSocketProtocol)

    def test_websocket_missing_close_fails(self) -> None:
        class NoClose:
            async def accept(self, subprotocol: str | None = None) -> None: ...

            async def receive_text(self) -> str: ...

            async def receive_json(self) -> Any: ...

            async def send_text(self, data: str) -> None: ...

            async def send_json(self, data: Any) -> None: ...

        assert not isinstance(NoClose(), WebSocketProtocol)


class TestServiceInfo:
    def test_fields(self) -> None:
        info = _info("api", "10.0.0.1", 9000)
        assert info.name == "api"
        assert info.host == "10.0.0.1"
        assert info.port == 9000
        assert info.metadata is None

    def test_metadata(self) -> None:
        info = ServiceInfo(name="a", host="h", port=1, metadata={"zone": "ph"})
        assert info.metadata == {"zone": "ph"}


class TestBehavior:
    async def test_registry_lifecycle(self) -> None:
        class R:
            def __init__(self) -> None:
                self.store: dict[str, list[ServiceInfo]] = {}

            async def register(self, service: ServiceInfo) -> None:
                self.store.setdefault(service.name, []).append(service)

            async def deregister(self, service_name: str, host: str, port: int) -> None:
                self.store[service_name] = [
                    s for s in self.store[service_name] if not (s.host == host and s.port == port)
                ]

            async def discover(self, service_name: str) -> list[ServiceInfo]:
                return list(self.store.get(service_name, []))

            async def get_service(
                self, service_name: str, host: str, port: int
            ) -> ServiceInfo | None:
                for s in self.store.get(service_name, []):
                    if s.host == host and s.port == port:
                        return s
                return None

            async def list_services(self) -> list[str]:
                return sorted(self.store)

        reg = R()
        await reg.register(_info("api", "h1", 1))
        await reg.register(_info("api", "h2", 2))
        await reg.register(_info("web", "h3", 3))
        assert len(await reg.discover("api")) == 2
        assert (await reg.get_service("api", "h2", 2)).host == "h2"
        assert await reg.get_service("api", "h9", 9) is None
        await reg.deregister("api", "h1", 1)
        assert [s.host for s in await reg.discover("api")] == ["h2"]
        assert (await reg.list_services()) == ["api", "web"]

    async def test_selector_round_robin(self) -> None:
        class RR:
            def __init__(self, instances: list[ServiceInfo]) -> None:
                self._instances = instances
                self._i = 0

            async def select(self, instances: list[ServiceInfo]) -> ServiceInfo | None:
                if not self._instances:
                    return None
                pick = self._instances[self._i % len(self._instances)]
                self._i += 1
                return pick

        sel = RR([_info("a", "h1", 1), _info("a", "h2", 2)])
        picks = [await sel.select([]) for _ in range(4)]
        assert [p.host for p in picks] == ["h1", "h2", "h1", "h2"]
        assert await RR([]).select([]) is None

    async def test_interceptor_chain_ordering(self) -> None:
        class Chain:
            def __init__(self) -> None:
                self._interceptors: list[InterceptorProtocol] = []

            def add_interceptor(self, interceptor: InterceptorProtocol) -> None:
                self._interceptors.append(interceptor)

            def remove_interceptor(self, interceptor: InterceptorProtocol) -> None:
                self._interceptors.remove(interceptor)

            async def process_request(self, context: Any) -> Any:
                for interceptor in self._interceptors:
                    context = await interceptor.intercept_request(context)
                return context

            async def process_response(self, response: Any) -> Any:
                for interceptor in self._interceptors:
                    response = await interceptor.intercept_response(response)
                return response

        class Tag:
            def __init__(self, tag: str) -> None:
                self.tag = tag

            async def intercept_request(self, context: str) -> str:
                return f"{context}+{self.tag}"

            async def intercept_response(self, response: str) -> str:
                return f"{self.tag}>{response}"

        chain = Chain()
        first = Tag("a")
        second = Tag("b")
        chain.add_interceptor(first)
        chain.add_interceptor(second)
        assert await chain.process_request("x") == "x+a+b"
        assert await chain.process_response("y") == "b>a>y"
        chain.remove_interceptor(first)
        assert len(chain._interceptors) == 1
        assert await chain.process_request("x") == "x+b"

    async def test_metrics_recorder(self) -> None:
        class M:
            def __init__(self) -> None:
                self.records: list[tuple] = []

            def record_request(
                self, service: str, method: str, duration: float, status: int
            ) -> None:
                self.records.append((service, method, duration, status))

            def get_metrics(self, service: str) -> dict[str, Any]:
                rows = [r for r in self.records if r[0] == service]
                return {"count": len(rows)}

        m = M()
        m.record_request("api", "GET", 0.1, 200)
        m.record_request("api", "POST", 0.2, 500)
        m.record_request("web", "GET", 0.3, 200)
        assert m.get_metrics("api") == {"count": 2}
        assert m.get_metrics("web") == {"count": 1}

    async def test_websocket_round_trip(self) -> None:
        class WS:
            def __init__(self) -> None:
                self.inbox: list[str] = []
                self.outbox: list[Any] = []
                self.accepted: str | None = None
                self.closed: tuple[int, str] | None = None

            async def accept(self, subprotocol: str | None = None) -> None:
                self.accepted = subprotocol

            async def receive_text(self) -> str:
                return self.inbox.pop(0)

            async def receive_json(self) -> Any:
                import json

                return json.loads(self.inbox.pop(0))

            async def send_text(self, data: str) -> None:
                self.outbox.append(data)

            async def send_json(self, data: Any) -> None:
                self.outbox.append(("json", data))

            async def close(self, code: int = 1000, reason: str = "") -> None:
                self.closed = (code, reason)

        ws = WS()
        await ws.accept("graphql-transport-ws")
        assert ws.accepted == "graphql-transport-ws"
        ws.inbox = ['{"op": "next"}', "plain"]
        assert await ws.receive_json() == {"op": "next"}
        assert await ws.receive_text() == "plain"
        await ws.send_text("hello")
        await ws.send_json({"k": 1})
        assert ws.outbox == ["hello", ("json", {"k": 1})]
        await ws.close(1011, "oom")
        assert ws.closed == (1011, "oom")
        ws2 = WS()
        await ws2.close()
        assert ws2.closed == (1000, "")


class TestExports:
    def test_all_exports(self) -> None:
        from quadkit.contracts import web

        names = [
            "ConnectMetricsCollectorProtocol",
            "HTTPClientProtocol",
            "HTTPSessionProtocol",
            "InterceptorChainProtocol",
            "InterceptorProtocol",
            "SelectorProtocol",
            "ServiceInfo",
            "ServiceMeshRegistryProtocol",
            "WebSocketProtocol",
        ]
        for name in names:
            assert hasattr(web, name), name
