"""Bare ASGI middleware classes compose into the stack (QK-5)."""

from __future__ import annotations

from typing import Any

import pytest
from starlette.applications import Starlette
from starlette.middleware import Middleware as StarletteMiddleware
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from quadkit.web.middleware.adapter import _QuadkitMiddlewareAdapter
from quadkit.web.middleware.registry import MiddlewareAdapterRegistry


class _NativeASGIMiddleware:
    """Canonical ASGI class: ``__init__(self, app)`` plus ``__call__``."""

    def __init__(self, app: Any) -> None:
        self.app = app
        self.calls: list[str] = []

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        self.calls.append(scope.get("path", ""))
        await self.app(scope, receive, send)


class _NotCallableMiddleware:
    """Class whose instances are not callable — a user error worth naming."""

    def __init__(self, app: Any) -> None:
        self.app = app


async def _ping(request: Any) -> PlainTextResponse:
    """Return a fixed payload."""
    return PlainTextResponse("pong")


def _build(middleware: Any) -> Starlette:
    """Wrap a route with the Quadkit adapter for the given middleware."""
    return Starlette(
        middleware=[
            StarletteMiddleware(_QuadkitMiddlewareAdapter, quadkit_mw=middleware)
        ],
        routes=[Route("/ping", _ping, methods=["GET"])],
    )


def test_bare_asgi_class_is_instantiated_with_the_app() -> None:
    """A bare ASGI class composes instead of failing on ``__init__`` arity."""
    client = TestClient(_build(_NativeASGIMiddleware))
    response = client.get("/ping")

    assert response.status_code == 200
    assert response.text == "pong"


def test_bare_asgi_class_sees_every_scope() -> None:
    """The instantiated middleware wraps the downstream app."""
    seen: list[str] = []

    class _RecordingASGIMiddleware:
        """ASGI class that records the scopes it observes."""

        def __init__(self, app: Any) -> None:
            self.app = app

        async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
            seen.append(scope.get("path", ""))
            await self.app(scope, receive, send)

    client = TestClient(_build(_RecordingASGIMiddleware))
    client.get("/ping")
    client.get("/ping")

    assert seen == ["/ping", "/ping"]


def test_non_callable_class_raises_actionable_error() -> None:
    """A class whose instances are not callable reports a clear message."""
    client = TestClient(_build(_NotCallableMiddleware), raise_server_exceptions=True)
    with pytest.raises(TypeError, match="not a usable ASGI middleware"):
        client.get("/ping")


def test_functional_middleware_still_uses_call_next() -> None:
    """Non-class callables keep the ``(request, call_next)`` contract."""
    seen: list[str] = []

    async def functional(request: Any, call_next: Any) -> Any:
        seen.append(str(request.url.path))
        return await call_next(request)

    client = TestClient(_build(functional))
    response = client.get("/ping")

    assert response.status_code == 200
    assert seen == ["/ping"]


def test_registry_falls_back_to_the_quadkit_adapter() -> None:
    """A bare class still routes through MiddlewareAdapterRegistry.adapt()."""
    registry = MiddlewareAdapterRegistry.with_defaults()
    adapted = registry.adapt(_NativeASGIMiddleware)

    assert adapted.cls is _QuadkitMiddlewareAdapter
    assert adapted.kwargs["quadkit_mw"] is _NativeASGIMiddleware
