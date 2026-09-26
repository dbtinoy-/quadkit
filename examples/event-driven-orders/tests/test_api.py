"""REST endpoint tests for the event-driven orders demo.

Boots ``OrdersModule`` (events + web wiring) through the real container and
drives the framework-mounted routes via an ``httpx.AsyncClient`` over
``WebProvider.starlette`` -- mirroring how ``main.py serve`` mounts them.
"""

from __future__ import annotations

from typing import AsyncIterator

import httpx
import pytest

from quadkit.app import Application
from quadkit.web.di.provider import WebProvider

from orders.app import create_app


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    application = create_app()
    await application.start()
    try:
        web = await application.container.resolve(WebProvider)
        transport = httpx.ASGITransport(app=web.starlette)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as http:
            yield http
    finally:
        await application.stop()


def _place_payload(customer: str = "Alice") -> dict[str, object]:
    return {
        "customer": customer,
        "items": [{"sku": "SKU-1", "qty": 2, "unit_price": "9.99"}],
    }


async def test_ship_unpaid_problem_type_names_the_domain_error(
    client: httpx.AsyncClient,
) -> None:
    # @error_status(OrderNotPaidError, 409) maps the demo's own error type:
    # the ProblemDetail type URN derives from the domain class name, not the
    # generic contracts conflict slug.
    order_id = (
        await client.post("/orders", json=_place_payload("Bob"))
    ).json()["order_id"]

    response = await client.post(f"/orders/{order_id}/ship")

    assert response.status_code == 409
    assert response.json()["type"] == "urn:quadkit:order-not-paid"


async def test_place_pay_ship_over_http(client: httpx.AsyncClient) -> None:
    placed = await client.post("/orders", json=_place_payload())
    assert placed.status_code == 201
    order_id = placed.json()["order_id"]
    assert placed.json()["status"] == "placed"

    paid = await client.post(f"/orders/{order_id}/pay", json={"amount": "19.98"})
    assert paid.status_code == 200

    shipped = await client.post(f"/orders/{order_id}/ship")
    assert shipped.status_code == 200

    # Read-side projections advance when the transactional outbox flushes.
    await client.post("/outbox/flush")

    row = (await client.get(f"/orders/{order_id}")).json()
    assert row["status"] == "shipped"


async def test_ship_unpaid_maps_to_409(client: httpx.AsyncClient) -> None:
    order_id = (
        await client.post("/orders", json=_place_payload("Bob"))
    ).json()["order_id"]

    response = await client.post(f"/orders/{order_id}/ship")

    assert response.status_code == 409
    assert "paid" in response.json()["detail"].lower()


async def test_unknown_order_maps_to_404(client: httpx.AsyncClient) -> None:
    missing = await client.get("/orders/nope")
    assert missing.status_code == 404

    shipped = await client.post("/orders/nope/ship")
    assert shipped.status_code == 404


async def test_place_validates_payload(client: httpx.AsyncClient) -> None:
    no_items = await client.post("/orders", json={"customer": "C"})
    assert no_items.status_code == 422

    bad_item = await client.post(
        "/orders",
        json={"customer": "C", "items": [{"qty": "x"}]},
    )
    assert bad_item.status_code == 422

    no_customer = await client.post("/orders", json={"items": []})
    assert no_customer.status_code == 422


async def test_list_and_get_read_model(client: httpx.AsyncClient) -> None:
    order_id = (await client.post("/orders", json=_place_payload())).json()[
        "order_id"
    ]
    await client.post("/outbox/flush")  # publish staged events to the read side

    rows = (await client.get("/orders")).json()
    assert any(row["order_id"] == order_id for row in rows)


async def test_outbox_inspection_and_flush(client: httpx.AsyncClient) -> None:
    order_id = (await client.post("/orders", json=_place_payload())).json()[
        "order_id"
    ]
    await client.post(f"/orders/{order_id}/pay", json={"amount": "19.98"})

    staged = (await client.get("/outbox")).json()
    assert isinstance(staged, list) and staged

    flushed = (await client.post("/outbox/flush")).json()
    assert flushed["ok"] is True
    assert flushed["flushed"] >= len(staged)


async def test_guided_demo_runs_over_http(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/demo")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "shipped"
    assert body["order_id"]
