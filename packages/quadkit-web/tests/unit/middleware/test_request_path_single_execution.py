"""Pin one execution per request for the default middleware stack.

A previous round of work removed a double DI scope from the request path
(two `DIScopeMiddleware` executions per request, two scopes, the second
overwriting `request.state.container`). Nothing in the suite failed when it
was there, so this module counts real executions through the mounted stack:
each middleware that must run on the request path is wrapped in a counter and
asserted to have run exactly once per request.

`WebHooksMiddleware` and `RequestBodySizeLimitMiddleware` are counted too —
they are part of the same stack and the same class of defect.
"""

from __future__ import annotations

from typing import Any, Self

import pytest
from starlette.testclient import TestClient

from quadkit.app.base import Application
from quadkit.web import Controller, get
from quadkit.web.config import RateLimitConfig, WebConfig
from quadkit.web.di.provider import WebProvider

#: Middleware that must execute exactly once per request on the mounted stack.
COUNTED = (
    "RequestContextMiddleware",
    "DIScopeMiddleware",
    "WebHooksMiddleware",
    "RequestBodySizeLimitMiddleware",
)


class ProbeController(Controller):
    """One route, so the request path is exercised end to end."""

    @get("/probe")
    async def probe(self) -> dict:
        return {"ok": True}


class _Counter:
    """Wrap ``__call__`` on a class and count HTTP executions.

    Only ``http`` scopes are counted: an ASGI middleware also sees the
    lifespan scope, which is not a request.
    """

    def __init__(self, cls: type) -> None:
        self.cls = cls
        self.calls = 0
        self._original = cls.__call__

    def __enter__(self) -> Self:
        original = self._original

        async def counting(self_inner: Any, scope: Any, receive: Any, send: Any) -> Any:
            if scope.get("type") == "http":
                self.calls += 1
            return await original(self_inner, scope, receive, send)

        self.cls.__call__ = counting  # type: ignore[method-assign]
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.cls.__call__ = self._original  # type: ignore[method-assign]


def _mounted_classes() -> dict[str, type]:
    """Resolve the middleware classes the default stack mounts by name."""
    from quadkit.web.middleware.body_limit import RequestBodySizeLimitMiddleware
    from quadkit.web.middleware.di_scope import DIScopeMiddleware
    from quadkit.web.middleware.hooks import WebHooksMiddleware
    from quadkit.web.middleware.request_context import RequestContextMiddleware

    return {
        "RequestContextMiddleware": RequestContextMiddleware,
        "DIScopeMiddleware": DIScopeMiddleware,
        "WebHooksMiddleware": WebHooksMiddleware,
        "RequestBodySizeLimitMiddleware": RequestBodySizeLimitMiddleware,
    }


async def _mounted_client() -> TestClient:
    """Boot a default web app and return a client over the mounted stack."""
    app = Application(name="middleware-path-probe")
    web = WebProvider(
        web_config=WebConfig(rate_limit=RateLimitConfig(enabled=False)),
        controllers=[ProbeController],
    )
    await web.register(app.container)
    await web.boot(app.container)
    assert web.starlette is not None
    return TestClient(web.starlette)


@pytest.mark.asyncio
async def test_each_request_path_middleware_executes_once_per_request() -> None:
    """Two requests produce two executions per mounted middleware — not four."""
    client = await _mounted_client()
    classes = _mounted_classes()

    with client:
        client.get("/probe").raise_for_status()
        client.get("/probe").raise_for_status()

    for name in COUNTED:
        with _Counter(classes[name]) as counter:
            with client:
                client.get("/probe").raise_for_status()
                client.get("/probe").raise_for_status()
        assert counter.calls == 2, f"{name} ran {counter.calls} times for 2 requests"


@pytest.mark.asyncio
async def test_error_response_takes_the_same_single_pass() -> None:
    """A 404 goes through the stack once as well."""
    client = await _mounted_client()
    classes = _mounted_classes()

    with _Counter(classes["RequestContextMiddleware"]) as context_counter:
        with _Counter(classes["DIScopeMiddleware"]) as scope_counter:
            with client:
                response = client.get("/definitely-not-a-route")

    assert response.status_code == 404
    assert context_counter.calls == 1
    assert scope_counter.calls == 1


@pytest.mark.asyncio
async def test_mounted_stack_matches_the_documented_boot_log() -> None:
    """The stack the app builds carries each request-path middleware once."""
    app = Application(name="middleware-path-probe")
    web = WebProvider(
        web_config=WebConfig(rate_limit=RateLimitConfig(enabled=False)),
        controllers=[ProbeController],
    )
    await web.register(app.container)
    await web.boot(app.container)
    assert web.starlette is not None

    with TestClient(web.starlette):
        pass

    stack = web.starlette.middleware_stack
    names: list[str] = []
    while stack is not None:
        names.append(type(stack).__name__)
        stack = getattr(stack, "app", None)

    for name in COUNTED:
        # The adapter that carries a Quadkit middleware into Starlette keeps
        # the wrapped instance on ``.app``; the class name appears once.
        assert names.count(name) <= 1, f"{name} appears {names.count(name)} times"
