import pytest
from starlette.types import Scope

from quadkit.contracts.core.trace_context import span_id_var, trace_id_var
from quadkit.primitives.context import (
    Context,
    create_default_context,
    get_request_context,
)
from quadkit.web.middleware.request_context import RequestContextMiddleware


@pytest.mark.asyncio
async def test_request_context_middleware_extracts_traceparent() -> None:
    """Test that RequestContextMiddleware extracts traceparent correctly."""

    async def app(scope, receive, send):
        assert trace_id_var.get() == "4bf92f3577b34da6a3ce929d0e0e4736"
        assert span_id_var.get() is not None

        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": b'{"ok": true}',
            }
        )

    middleware = RequestContextMiddleware(app)

    scope: Scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [
            (
                b"traceparent",
                b"00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
            )
        ],
    }

    async def receive():
        return {"type": "http.request"}

    response_started = False

    async def send(message):
        nonlocal response_started
        if message["type"] == "http.response.start":
            response_started = True

    await middleware(scope, receive, send)
    assert response_started


@pytest.mark.asyncio
async def test_request_context_middleware_generates_generic_trace() -> None:
    """Test that RequestContextMiddleware generates trace_id even without header."""

    async def app(scope, receive, send):
        assert trace_id_var.get() is not None
        assert len(trace_id_var.get()) == 32

        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    middleware = RequestContextMiddleware(app)

    scope: Scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
    }

    async def receive():
        return {"type": "http.request"}

    async def send(message):
        return None

    await middleware(scope, receive, send)


@pytest.mark.asyncio
async def test_request_context_middleware_prefers_state_tenant_over_header() -> None:
    context: Context = create_default_context()

    async def app(scope, receive, send):
        current = get_request_context(context.registry)
        assert current is not None
        assert current.tenant_id == "tenant-from-state"
        assert current.user_id == "user-7"
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    middleware = RequestContextMiddleware(app, context=context)
    scope: Scope = {
        "type": "http",
        "method": "GET",
        "path": "/pets",
        "headers": [(b"x-tenant-id", b"tenant-from-header")],
        "state": {"tenant_id": "tenant-from-state", "user_id": "user-7"},
    }

    async def receive():
        return {"type": "http.request"}

    async def send(_message):
        return None

    await middleware(scope, receive, send)


@pytest.mark.asyncio
async def test_request_context_middleware_uses_shared_context_registry() -> None:
    context: Context = create_default_context()

    async def app(scope, receive, send):
        current = get_request_context(context.registry)
        assert current is not None
        assert current.request_id == "req_shared"
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    middleware = RequestContextMiddleware(app, context=context)
    scope: Scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [(b"x-request-id", b"req_shared")],
        "state": {},
    }

    async def receive():
        return {"type": "http.request"}

    async def send(_message):
        return None

    await middleware(scope, receive, send)
