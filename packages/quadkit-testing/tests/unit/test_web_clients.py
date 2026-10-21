"""Tests for the web test client (``WebTestClient``/``TestResponse``) and bed.

Exercises the full assertion surface of :class:`TestResponse`, every HTTP
verb of :class:`WebTestClient` against a real Starlette ASGI app, user
simulation, WebSocket support, and the three constructor branches of
:class:`WebTestBed` (raw ASGI callable, WebProvider, Application).
"""

from __future__ import annotations

from typing import Any

import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.routing import Route, WebSocketRoute

from quadkit.testing.clients.web.bed import WebTestBed, with_web
from quadkit.testing.clients.web.client import TestResponse, WebTestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeResponse:
    """Minimal stand-in for an HTTPX response object."""

    def __init__(self, status_code: int = 200, payload: Any = None, text: str = ""):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text or str(payload)
        self.headers = {"content-type": "application/json", "x-test": "yes"}
        self.cookies = {"session": "abc123"}

    def json(self) -> Any:
        return self._payload


def _starlette_app() -> Starlette:
    """Build a small ASGI app exercising every HTTP verb and a websocket."""

    async def get_json(request: Any) -> JSONResponse:
        return JSONResponse({"data": {"user": {"id": 7}}, "items": ["a", "b"]})

    async def echo(request: Any) -> JSONResponse:
        raw = await request.body()
        import json as _json

        body = _json.loads(raw) if raw else None
        return JSONResponse(
            {
                "method": request.method,
                "body": body,
                "user_id": request.headers.get("X-User-ID"),
                "custom": request.headers.get("X-Custom"),
            }
        )

    async def text(request: Any) -> PlainTextResponse:
        return PlainTextResponse("hello-web", headers={"X-Plain": "1"})

    async def cookie(request: Any) -> PlainTextResponse:
        response = PlainTextResponse("ok")
        response.set_cookie("issued", "yes")
        return response

    async def websocket_endpoint(websocket: Any) -> None:
        await websocket.accept()
        data = await websocket.receive_text()
        await websocket.send_text(f"echo:{data}")
        await websocket.close()

    return Starlette(
        routes=[
            Route("/json", get_json, methods=["GET", "OPTIONS"]),
            Route("/echo", echo, methods=["POST", "PUT", "PATCH"]),
            Route("/text", text),
            Route("/echo-delete", echo, methods=["DELETE"]),
            Route("/cookie", cookie),
            WebSocketRoute("/ws", websocket_endpoint),
        ]
    )


# ---------------------------------------------------------------------------
# TestResponse
# ---------------------------------------------------------------------------


def test_response_properties() -> None:
    response = TestResponse(_FakeResponse(201, {"a": 1}, "raw"))
    assert response.status_code == 201
    assert response.json == {"a": 1}
    assert response.text == "raw"
    assert response.headers["x-test"] == "yes"
    assert response.cookies == {"session": "abc123"}


def test_assert_status_pass_and_fail() -> None:
    response = TestResponse(_FakeResponse(200))
    assert response.assert_status(200) is response
    with pytest.raises(AssertionError, match="Expected status 404"):
        response.assert_status(404)


def test_assert_json_path_nested_dict_and_list() -> None:
    response = TestResponse(_FakeResponse(200, {"data": {"user": {"id": 7}}, "items": ["a", "b"]}))
    response.assert_json_path("data.user.id", 7)
    response.assert_json_path("items.1", "b")
    # Non-list index and missing keys resolve to None
    response.assert_json_path("items.abc", None)
    response.assert_json_path("missing.key", None)
    with pytest.raises(AssertionError, match="data.user.id="):
        response.assert_json_path("data.user.id", 8)


def test_assert_header_case_insensitive() -> None:
    response = TestResponse(_FakeResponse())
    response.assert_header("X-Test", "yes")
    response.assert_header("x-test", "yes")
    with pytest.raises(AssertionError, match="X-Missing"):
        response.assert_header("X-Missing", "nope")


def test_assert_json_exact() -> None:
    response = TestResponse(_FakeResponse(200, {"a": 1, "b": 2}))
    assert response.assert_json({"a": 1, "b": 2}) is response
    with pytest.raises(AssertionError):
        response.assert_json({"a": 1})


async def test_response_is_awaitable() -> None:
    response = TestResponse(_FakeResponse())
    awaited = await response
    assert awaited is response


# ---------------------------------------------------------------------------
# WebTestClient against a real ASGI app
# ---------------------------------------------------------------------------


@pytest.fixture
def client() -> WebTestClient:
    return WebTestClient(_starlette_app())


def test_get_and_assertions(client: WebTestClient) -> None:
    response = client.get("/json")
    response.assert_status(200).assert_json_path("data.user.id", 7)
    assert response.status_code == 200


def test_text_endpoint_and_header_assertion(client: WebTestClient) -> None:
    response = client.get("/text")
    assert response.text == "hello-web"
    response.assert_header("X-Plain", "1")


def test_post_put_patch_echo(client: WebTestClient) -> None:
    response = client.post("/echo", json={"v": 1})
    response.assert_status(200).assert_json_path("method", "POST")
    response.assert_json_path("body.v", 1)

    put = client.put("/echo", json={"v": 2})
    put.assert_json_path("method", "PUT")

    patch = client.patch("/echo", json={"v": 3})
    patch.assert_json_path("method", "PATCH")


def test_delete_and_options_head(client: WebTestClient) -> None:
    client.delete("/echo-delete").assert_status(200)
    client.options("/json").assert_status(200)
    client.head("/json").assert_status(200)


def test_generic_request_with_headers(client: WebTestClient) -> None:
    response = client.request(
        "POST", "/echo", headers={"X-Custom": "c1"}, json={"v": 9}
    )
    response.assert_json_path("custom", "c1")
    response.assert_json_path("body.v", 9)


def test_as_user_injects_x_user_id(client: WebTestClient) -> None:
    class _User:
        id = "user-42"

    response = client.as_user(_User()).post("/echo", json={})
    response.assert_json_path("user_id", "user-42")
    # as_user is fluent
    assert client.as_user("plain-string").post("/echo", json={}).json["user_id"] == (
        "plain-string"
    )


def test_websocket_connect(client: WebTestClient) -> None:
    with client.websocket_connect("/ws") as socket:
        socket.send_text("ping")
        assert socket.receive_text() == "echo:ping"


def test_context_manager() -> None:
    with WebTestClient(_starlette_app()) as client:
        client.get("/json").assert_status(200)


def test_extract_asgi_app_raw_callable() -> None:
    async def asgi(scope: Any, receive: Any, send: Any) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"text/plain")],
            }
        )
        await send({"type": "http.response.body", "body": b"hi"})

    # Raw ASGI callables pass through _extract_asgi_app unchanged
    client = WebTestClient(asgi)
    assert client._client is not None


# ---------------------------------------------------------------------------
# WebTestBed
# ---------------------------------------------------------------------------


def test_bed_with_raw_asgi_builds_client_eagerly() -> None:
    async def asgi(scope: Any, receive: Any, send: Any) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send({"type": "http.response.body", "body": b'{"ok": true}'})

    bed = WebTestBed(asgi)
    # Client is usable without an async setup round-trip
    response = bed.get("/")
    response.assert_status(200).assert_json({"ok": True})
    assert bed.client is not None


async def test_bed_convenience_methods_raw_asgi() -> None:
    async def asgi(scope: Any, receive: Any, send: Any) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": 201,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send({"type": "http.response.body", "body": b'{"n": 1}'})

    bed = WebTestBed(asgi)
    bed.post("/").assert_status(201)
    bed.put("/").assert_status(201)
    bed.patch("/").assert_status(201)
    bed.delete("/").assert_status(201)


async def test_bed_context_manager_with_application() -> None:
    from quadkit.app.base import Application
    from quadkit.web.di.provider import WebProvider

    app = Application("web-bed-app")
    provider = WebProvider()
    app.add_provider(provider)

    bed = with_web(app)
    assert bed.web_provider is provider

    async with bed:
        client = bed.client
        assert isinstance(client, WebTestClient)

    # after aexit the environment is torn down
    assert bed is not None


def test_bed_override_is_fluent() -> None:
    from quadkit.app.base import Application

    app = Application("web-bed-override")
    bed = WebTestBed(app)
    sentinel = object()

    class _Interface:
        pass

    assert bed.override(_Interface, sentinel) is bed


async def test_bed_with_web_provider_instance() -> None:
    """A WebProvider passed directly becomes the bed's provider."""
    from quadkit.web.di.provider import WebProvider

    provider = WebProvider()
    bed = WebTestBed(provider)
    assert bed.web_provider is provider


def test_a_cookie_the_response_set_is_readable() -> None:
    """An app whose behaviour *is* a cookie has to be assertable.

    Session identity, per-visitor scoping, "these two callers are kept
    apart" — none of it can be tested through this client if the only way
    to a cookie is parsing the raw `set-cookie` header, because the
    underlying response is private.
    """
    client = WebTestClient(_starlette_app())

    response = client.get("/cookie")

    assert response.cookies["issued"] == "yes"
