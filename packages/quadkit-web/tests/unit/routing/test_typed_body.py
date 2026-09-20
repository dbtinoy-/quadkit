"""Tests for typed body injection in the script-mode route wrapper.

Verifies that :func:`~quadkit.web.routing.route_handlers._wrap_script_handler`
correctly deserialises a JSON request body into:
- A Pydantic ``BaseModel`` subclass
- Returns HTTP 422 when the Pydantic model validation fails
"""

# NOTE: Do NOT add ``from __future__ import annotations`` here.
# The _wrap_script_handler inspects annotation objects at runtime via
# ``inspect.signature``; postponed evaluation (PEP 563) turns them into
# strings, breaking isinstance/issubclass checks at parameter-binding time.

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from quadkit.web.quickstart import _PendingRoute, _QuickstartApp


# ---------------------------------------------------------------------------
# Shared Pydantic model
# ---------------------------------------------------------------------------


class CreateItemRequest(BaseModel):
    """Request body model used in typed-body injection tests."""

    name: str
    price: float


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


async def _make_client(routes: list[_PendingRoute]) -> AsyncClient:
    """Boot a fresh ``_QuickstartApp`` and return a client.

    Args:
        routes: The routes to expose on the freshly-created app.

    Returns:
        An :class:`httpx.AsyncClient` targeting the booted Starlette app.
    """
    quickstart_app = _QuickstartApp()
    quickstart_app._collect_script_routes = lambda: routes
    await quickstart_app._ensure_booted()
    return AsyncClient(
        transport=ASGITransport(app=quickstart_app._starlette),
        base_url="http://test",
    )


# ---------------------------------------------------------------------------
# Test 1 — valid Pydantic body is injected as a model instance
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pydantic_body_injection() -> None:
    """POST with a valid JSON body injects a populated Pydantic model instance.

    Asserts that the handler receives a ``CreateItemRequest`` with the correct
    ``name`` and ``price`` fields parsed from the request body.
    """

    async def create_item(item: CreateItemRequest) -> dict:
        return {"name": item.name, "price": item.price}

    routes = [_PendingRoute(path="/items", method="POST", handler=create_item)]

    async with await _make_client(routes) as client:
        response = await client.post("/items", json={"name": "widget", "price": 4.99})

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "widget"
    assert data["price"] == pytest.approx(4.99)


# ---------------------------------------------------------------------------
# Test 2 — invalid Pydantic body returns 422
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pydantic_body_validation_error_returns_422() -> None:
    """POST with a body missing required Pydantic fields returns HTTP 422.

    ``CreateItemRequest`` requires both ``name`` and ``price``.  Sending a body
    that omits ``price`` should trigger Pydantic ``ValidationError`` and the
    wrapper must convert it to a JSON 422 response with an ``errors`` key.
    """

    async def create_item(item: CreateItemRequest) -> dict:
        return {"name": item.name, "price": item.price}

    routes = [_PendingRoute(path="/items", method="POST", handler=create_item)]

    async with await _make_client(routes) as client:
        # Missing required field "price"
        response = await client.post("/items", json={"name": "widget"})

    assert response.status_code == 422
    body = response.json()
    assert "errors" in body
    assert isinstance(body["errors"], list)
    assert len(body["errors"]) > 0
