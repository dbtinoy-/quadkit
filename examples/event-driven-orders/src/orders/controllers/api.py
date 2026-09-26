"""Convention followed: **Controller pattern** — stateless HTTP adapters; services return ``Result[T, E]``; failures map to RFC-9457 ``ProblemDetail``.

REST surface for the event-driven orders demo.

Maps the ``OrdersApi`` facade onto HTTP so the CQRS lifecycle can be driven
from a browser or curl:

- ``POST /orders``                       — place an order
- ``GET /orders`` / ``GET /orders/{id}`` — read-model queries
- ``POST /orders/{id}/pay|ship``         — lifecycle commands
- ``GET /outbox`` / ``POST /outbox/flush`` — transactional outbox inspection
- ``POST /api/demo``                    — run the full lifecycle in one call

The controller registers the demo's own error vocabulary with the Result
bridge via ``@error_status``, so lifecycle handlers surface facade errors
as-is: unknown order -> 404, state conflicts -> 409, remaining ``OrderError``
subclasses -> 400 through the ``DomainError`` fallback. No handler re-expresses
a domain error as a contracts base class just to pick an HTTP status.

Payload parsing for ``place_order``/``pay`` is intentionally explicit rather
than DTO-bound: prices and amounts are ``Decimal`` values, and the request
binder does not coerce strings to ``Decimal`` (only to simple scalars), so
the demo converts money at the boundary itself.
"""
# Controller pattern — each handler returns Result[T, E].
# The web pipeline renders Ok payloads as JSON and maps Err to
# ProblemDetail responses. Error types determine HTTP status codes.
# @error_status decorators register custom mappings for domain errors.

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from starlette.requests import Request

from orders.domain import (
    OrderAlreadyPaidError,
    OrderAlreadyShippedError,
    OrderError,
    OrderItem,
    OrderNotFoundError,
    OrderNotPaidError,
)
from orders.services.orders_api import OrdersApi
from quadkit.contracts.exceptions.domain import ValidationError
from quadkit.result import Err, Ok, Result
from quadkit.serialization import loads as json_loads
from quadkit.web import Controller, get, post
from quadkit.web.routing.result_bridge import error_status


# --- Error-to-HTTP mappings ---
# The @error_status decorator tells the Result bridge which HTTP status
# to use for each domain error type.  Unmapped errors fall through to
# the DomainError default (400).
@error_status(OrderNotFoundError, 404)
@error_status(OrderNotPaidError, 409)
@error_status(OrderAlreadyPaidError, 409)
@error_status(OrderAlreadyShippedError, 409)
class OrdersApiController(Controller):
    """Expose the order write/read sides over HTTP.

    Quadkit pattern: controllers are stateless handlers that receive
    collaborators via constructor injection.  The framework resolves the
    controller when a request matches its routes — you never instantiate
    it manually.

    Route decorators (@get, @post) come from quadkit.web, not Starlette
    directly — they integrate with the framework's middleware stack.
    """

    def __init__(self, api: OrdersApi) -> None:
        # Constructor injection — all dependencies are
        # explicit typed parameters. The provider wires these in boot().
        self.api = api

    @post("/orders", status_code=201)
    async def place_order(
        self,
        request: Request,
    ) -> Result[dict, ValidationError | OrderError]:
        """Place a new order from a JSON customer/items payload.

        Return type uses ``Result[T, E]`` — the web pipeline maps Err
        types to HTTP status codes automatically (ValidationError -> 422,
        OrderNotFoundError -> 404, OrderError -> 400).
        """
        # Parse JSON body — prices are Decimal, so we convert manually
        # rather than relying on the framework's request binder.
        body = json_loads(await request.body())
        customer = str(body.get("customer") or "").strip()
        if not customer:
            return Err(ValidationError("customer is required"))

        # Build OrderItem list from raw JSON — validate each item
        # explicitly since Decimal conversion can fail on bad input.
        parsed: list[OrderItem] = []
        for raw in body.get("items") or []:
            try:
                sku = str(raw["sku"])
                parsed.append(
                    OrderItem(
                        sku=sku,
                        name=sku,
                        qty=int(raw.get("qty", 1)),
                        unit_price=Decimal(str(raw.get("unit_price", "0"))),
                    )
                )
            except (KeyError, InvalidOperation, ValueError, TypeError) as exc:
                return Err(ValidationError(f"invalid item: {exc}"))
        if not parsed:
            return Err(ValidationError("at least one item is required"))

        # Dispatch through the facade — the command bus routes PlaceOrder
        # to PlaceOrderHandler, which persists and stages the event.
        placed = await self.api.place(customer=customer, items=parsed)
        if placed.is_err():
            return Err(placed.unwrap_err())
        order_id = placed.unwrap()
        return Ok({"order_id": order_id, "status": "placed"})

    @get("/orders")
    async def list_orders(self) -> list[dict]:
        """Return the projected read-model rows."""
        return self.api.list_orders()

    @get("/orders/{order_id}")
    async def get_order(
        self,
        order_id: str,
    ) -> Result[dict, OrderNotFoundError]:
        """Return one projected order row."""
        for row in self.api.list_orders():
            if row.get("order_id") == order_id:
                return Ok(row)
        return Err(OrderNotFoundError(f"unknown order {order_id}"))

    @post("/orders/{order_id}/pay")
    async def pay_order(
        self,
        order_id: str,
        request: Request,
    ) -> Result[dict, OrderError]:
        """Mark an order paid.

        The facade surfaces write-side rejections by raising; the
        boundary translates them into ``Err`` so the Result bridge —
        with the ``@error_status`` mappings above — renders them.
        """
        body = json_loads(await request.body())
        try:
            amount = Decimal(str(body.get("amount", "0")))
        except InvalidOperation:
            return Err(OrderError("invalid amount"))
        try:
            paid = await self.api.pay(order_id=order_id, amount=amount)
        except OrderError as exc:
            return Err(exc)
        if paid.is_err():
            return Err(paid.unwrap_err())
        return Ok({"ok": True})

    @post("/orders/{order_id}/ship")
    async def ship_order(
        self,
        order_id: str,
    ) -> Result[dict, OrderError]:
        """Mark an order shipped (requires the order to be paid)."""
        try:
            shipped = await self.api.ship(order_id)
        except OrderError as exc:
            return Err(exc)
        if shipped.is_err():
            return Err(shipped.unwrap_err())
        return Ok({"ok": True})

    @get("/outbox")
    async def list_outbox(self) -> list[dict]:
        """Return staged outbox records in order."""
        return self.api.list_outbox()

    @post("/outbox/flush")
    async def flush_outbox(self) -> Result[dict, Exception]:
        """Flush staged events through the event bus."""
        flushed = await self.api.flush_outbox()
        return flushed.map_sync(lambda count: {"ok": True, "flushed": count})

    @post("/api/demo")
    async def run_demo(self) -> Result[dict, OrderError]:
        """Run the full lifecycle in one call: place, pay, ship, flush.

        Runs the guided browser walkthrough over HTTP.  Returns the order id
        and final read-model row so the UI can display the result immediately.
        """
        # Place a sample order.
        from orders.domain import OrderItem as _Item

        items = [
            _Item(sku="SKU-1", name="SKU-1", qty=2, unit_price=Decimal("9.99")),
            _Item(sku="SKU-2", name="SKU-2", qty=1, unit_price=Decimal("149.00")),
        ]
        placed = await self.api.place("Alice Wonder", items)
        if placed.is_err():
            return Err(placed.unwrap_err())
        order_id = placed.unwrap()

        # Pay and ship.
        paid = await self.api.pay(order_id, Decimal("168.98"))
        if paid.is_err():
            return Err(paid.unwrap_err())
        shipped = await self.api.ship(order_id)
        if shipped.is_err():
            return Err(shipped.unwrap_err())

        # Flush the outbox so the read model advances.
        await self.api.flush_outbox()

        # Return the final read-model row.
        for row in self.api.list_orders():
            if row.get("order_id") == order_id:
                return Ok(row)
        return Ok({"order_id": order_id})


__all__ = ["OrdersApiController"]
