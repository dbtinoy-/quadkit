"""Convention followed: **Controller pattern** — stateless HTTP adapters;
services return domain values or raise; the controller translates outcomes
to ``Result``/HTTP responses.

REST surface for placing and reading orders.
"""

from __future__ import annotations

from starlette.requests import Request

from quadkit.result import Err, Ok, Result
from quadkit.serialization import loads as json_loads
from quadkit.web import Controller, get, post
from quadkit.web.routing.result_bridge import error_status
from storefront.modules.orders.exceptions import (
    InsufficientStockError,
    OrderError,
    OrderNotFoundError,
    UnknownProductError,
)
from storefront.modules.orders.services import OrderService


@error_status(OrderNotFoundError, 404)
@error_status(UnknownProductError, 422)
@error_status(InsufficientStockError, 409)
class OrdersApiController(Controller):
    """Expose order placement and lookup over HTTP.

    Depends on ``OrderService``, whose own constructor depends on
    ``ProductCatalogProtocol`` — the cross-module dependency this whole
    demo exists to demonstrate. This controller never imports anything
    from ``storefront.modules.catalog`` at all.
    """

    prefix = "/api/orders"

    def __init__(self, orders: OrderService) -> None:
        self.orders = orders

    @post("", status_code=201)
    async def place_order(self, request: Request) -> Result[dict, OrderError]:
        """Place an order from a JSON ``{customer, items: [{sku, qty}]}`` body."""
        body = json_loads(await request.body())
        customer = str(body.get("customer") or "").strip()
        if not customer:
            return Err(OrderError("customer is required"))

        items: list[tuple[str, int]] = []
        for raw in body.get("items") or []:
            try:
                items.append((str(raw["sku"]), int(raw.get("qty", 1))))
            except (KeyError, TypeError, ValueError) as exc:
                return Err(OrderError(f"invalid item: {exc}"))
        if not items:
            return Err(OrderError("at least one item is required"))

        try:
            order = await self.orders.place_order(customer, items)
        except OrderError as exc:
            return Err(exc)
        return Ok(order.to_payload())

    @get("")
    async def list_orders(self) -> list[dict]:
        """Return every placed order."""
        orders = await self.orders.list_all()
        return [o.to_payload() for o in orders]

    @get("/{order_id}")
    async def get_order(self, order_id: str) -> Result[dict, OrderNotFoundError]:
        """Return one order, or a 404 if unknown."""
        order = await self.orders.get(order_id)
        if order is None:
            return Err(OrderNotFoundError(f"unknown order {order_id}"))
        return Ok(order.to_payload())

    @post("/demo/run")
    async def run_demo(self) -> Result[dict, OrderError]:
        """Place a sample order to drive the guided browser walkthrough."""
        try:
            order = await self.orders.place_order(
                "Alice Wonder", [("MUG-001", 2), ("CAP-001", 1)]
            )
        except OrderError as exc:
            return Err(exc)
        return Ok(order.to_payload())


__all__ = ["OrdersApiController"]
