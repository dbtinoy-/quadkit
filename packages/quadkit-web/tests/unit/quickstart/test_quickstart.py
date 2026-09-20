"""Tests for the quickstart (Gear 1 / script-mode) ASGI helper.

Covers:
- A minimal ``@get`` handler that returns a JSON dict
- ``Request`` parameter injection into a route handler
- POST with a JSON body received as ``dict``

Each test creates a fresh :class:`~quadkit.web.quickstart._QuickstartApp`
instance and patches ``_collect_script_routes`` to supply only the routes
relevant to that test.  This prevents module-level state from leaking between
tests.
"""

# NOTE: Do NOT add ``from __future__ import annotations`` here.
# The _wrap_script_handler inspects annotation objects at runtime via
# ``inspect.signature``; postponed evaluation (PEP 563) turns them into
# strings, breaking the ``annotation is Request`` / ``annotation is dict``
# identity checks.

import pytest
from httpx import ASGITransport, AsyncClient
from starlette.requests import Request

from quadkit.web.quickstart import _PendingRoute, _QuickstartApp


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


async def _boot_and_client(quickstart_app: _QuickstartApp) -> AsyncClient:
    """Boot *quickstart_app* and return an ``AsyncClient`` wrapping its Starlette app.

    Args:
        quickstart_app: A freshly created, not-yet-booted instance.

    Returns:
        An :class:`httpx.AsyncClient` targeting the underlying Starlette app.
    """
    await quickstart_app._ensure_booted()
    return AsyncClient(
        transport=ASGITransport(app=quickstart_app._starlette),
        base_url="http://test",
    )


# ---------------------------------------------------------------------------
# Test 1 — minimal GET handler
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_6line_app_serves_response() -> None:
    """A bare ``@get("/")`` handler is served correctly by the quickstart app.

    Creates a handler at runtime, injects it via a patched
    ``_collect_script_routes``, boots the app, and asserts a 200 response with
    the expected JSON body.
    """

    async def hello() -> dict:
        return {"hello": "world"}

    quickstart_app = _QuickstartApp()
    quickstart_app._collect_script_routes = lambda: [
        _PendingRoute(path="/", method="GET", handler=hello)
    ]

    async with await _boot_and_client(quickstart_app) as client:
        response = await client.get("/")

    assert response.status_code == 200
    assert response.json() == {"hello": "world"}


# ---------------------------------------------------------------------------
# Test 2 — Request parameter injection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_quickstart_di_injection() -> None:
    """A handler that declares a ``Request`` param receives the live request object.

    Verifies that :func:`~quadkit.web.routing.route_handlers._wrap_script_handler`
    detects the ``Request`` annotation and passes the Starlette request through,
    allowing the handler to inspect it (e.g. read headers or method).
    """

    async def echo_method(req: Request) -> dict:
        return {"method": req.method}

    quickstart_app = _QuickstartApp()
    quickstart_app._collect_script_routes = lambda: [
        _PendingRoute(path="/echo", method="GET", handler=echo_method)
    ]

    async with await _boot_and_client(quickstart_app) as client:
        response = await client.get("/echo")

    assert response.status_code == 200
    assert response.json() == {"method": "GET"}


# ---------------------------------------------------------------------------
# Test 3 — POST with a JSON body received as dict
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_quickstart_post_with_body() -> None:
    """A POST handler with ``data: dict`` receives the parsed JSON body.

    Verifies that the script-mode wrapper reads the request body, parses it as
    JSON, and passes the resulting dict to the handler parameter annotated as
    ``dict``.
    """

    async def create_item(data: dict) -> dict:
        return {"received": data}

    quickstart_app = _QuickstartApp()
    quickstart_app._collect_script_routes = lambda: [
        _PendingRoute(path="/items", method="POST", handler=create_item)
    ]

    payload = {"name": "widget", "price": 9.99}

    async with await _boot_and_client(quickstart_app) as client:
        response = await client.post("/items", json=payload)

    assert response.status_code == 200
    assert response.json() == {"received": payload}


# ---------------------------------------------------------------------------
# Test 4 — @singleton auto-registration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_quickstart_singleton_service_injected() -> None:
    """A handler with a ``@singleton``-decorated service dependency gets it injected.

    The ``@singleton`` decorator marks the class with ``__quadkit_injectable__``.
    ``WebProvider._register_injectable_services`` scans sys.modules at boot time
    and auto-registers such classes in the DI container so handlers can declare
    them as type-hinted dependencies.
    """
    from quadkit.di import singleton

    @singleton
    class GreetingService:
        def greet(self, name: str) -> str:
            return f"Hello, {name}!"

    async def greet_handler(svc: GreetingService) -> dict:
        return {"message": svc.greet("Quadkit")}

    quickstart_app = _QuickstartApp()
    quickstart_app._collect_script_routes = lambda: [
        _PendingRoute(path="/greet", method="GET", handler=greet_handler)
    ]
    # Also expose the service through _collect_script_services so it's in scope
    quickstart_app._collect_script_services = lambda: [
        (GreetingService, "singleton")
    ]

    async with await _boot_and_client(quickstart_app) as client:
        response = await client.get("/greet")

    assert response.status_code == 200
    assert response.json() == {"message": "Hello, Quadkit!"}
