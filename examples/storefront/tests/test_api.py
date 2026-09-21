"""REST endpoint tests for the storefront demo.

Boots the real application via ``create_app()`` (both bounded-context
modules + web wiring) and drives the live routes through the ``client``
fixture from ``conftest.py`` — the controllers are discovered by
``WebModule.configure(discover=[...])``, so this test exercises the exact
routing path a browser would use.
"""

from __future__ import annotations

import httpx


async def test_catalog_lists_seeded_products(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/catalog/products")

    assert response.status_code == 200
    products = response.json()
    assert len(products) == 4
    assert {p["sku"] for p in products} == {"MUG-001", "TEE-001", "CAP-001", "STK-001"}


async def test_catalog_get_single_product(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/catalog/products/MUG-001")

    assert response.status_code == 200
    body = response.json()
    assert body["sku"] == "MUG-001"
    assert body["unit_price"] == "12.00"


async def test_catalog_unknown_product_reports_not_found(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get("/api/catalog/products/NOPE")

    assert response.status_code == 200
    assert response.json()["error"] == "not_found"


async def test_place_order_succeeds_and_reserves_stock(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post(
        "/api/orders",
        json={"customer": "Riley", "items": [{"sku": "MUG-001", "qty": 2}]},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["customer"] == "Riley"
    assert body["total"] == "24.00"
    assert body["order_id"].startswith("ORD-")

    # Stock was actually reserved through the cross-module dependency.
    product = (await client.get("/api/catalog/products/MUG-001")).json()
    assert product["stock"] == 38


async def test_place_order_missing_customer_is_rejected(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post(
        "/api/orders", json={"items": [{"sku": "MUG-001", "qty": 1}]}
    )

    assert response.status_code == 400


async def test_place_order_unknown_product_maps_to_422(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post(
        "/api/orders",
        json={"customer": "Riley", "items": [{"sku": "GHOST-1", "qty": 1}]},
    )

    assert response.status_code == 422


async def test_place_order_insufficient_stock_maps_to_409(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post(
        "/api/orders",
        json={"customer": "Riley", "items": [{"sku": "STK-001", "qty": 999}]},
    )

    assert response.status_code == 409


async def test_get_and_list_orders(client: httpx.AsyncClient) -> None:
    placed = await client.post(
        "/api/orders",
        json={"customer": "Riley", "items": [{"sku": "CAP-001", "qty": 1}]},
    )
    order_id = placed.json()["order_id"]

    fetched = await client.get(f"/api/orders/{order_id}")
    assert fetched.status_code == 200
    assert fetched.json()["order_id"] == order_id

    listed = await client.get("/api/orders")
    assert listed.status_code == 200
    assert any(o["order_id"] == order_id for o in listed.json())


async def test_get_unknown_order_maps_to_404(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/orders/ORD-9999")
    assert response.status_code == 404


async def test_guided_demo_runs_over_http(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/orders/demo/run")

    assert response.status_code == 200
    body = response.json()
    assert body["customer"] == "Alice Wonder"
    assert body["order_id"].startswith("ORD-")


async def test_page_console_served(client: httpx.AsyncClient) -> None:
    response = await client.get("/")

    assert response.status_code == 200
    assert "Storefront" in response.text
