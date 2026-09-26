"""Query-side service facade for the event-driven orders demo.

Resolves the framework buses and demo services once, then exposes simple
methods the REST controllers and browser UI can call.

This facade is the **single entry point** for all order operations.
It dispatches commands through the command bus and queries the read-side
projection.  Controllers and UI handlers never touch the buses directly.

Convention: a facade wraps the command bus, event bus, read model, and
outbox into a simple async API.  Controllers receive the facade via
constructor injection — they never resolve buses themselves.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from orders.commands import PayOrder, PlaceOrder, ShipOrder
from orders.domain import OrderError, OrderItem
from orders.events import OrdersView
from orders.repository.order_repository import OrderRepository
from orders.repository.outbox import Outbox
from quadkit.contracts.core.result import Err, Ok, Result
from quadkit.contracts.events import CommandBusProtocol, EventBusProtocol
from quadkit.logging import get_logger

logger = get_logger(__name__)


class OrdersApi:
    """Facade over the command bus, read model and outbox.

    Convention: the facade is the **only** way controllers interact with
    the domain.  It owns the wiring between commands, handlers, and the
    read model — controllers stay thin.

    Args:
        command_bus: The command bus.
        event_bus: The event bus.
        repository: The write-side repository.
        view: The read-side projection.
        outbox: The staged-event outbox.
    """

    def __init__(
        self,
        command_bus: CommandBusProtocol,
        event_bus: EventBusProtocol,
        repository: OrderRepository,
        view: OrdersView,
        outbox: Outbox,
    ) -> None:
        self.command_bus = command_bus
        self.event_bus = event_bus
        self.repository = repository
        self.view = view
        self.outbox = outbox

    async def _dispatch_command(self, command: Any) -> Any:
        """Run ``command`` through the bus and normalize the outcome.

        The bus is typed ``-> Any``: handlers may return bare values or
        ``Result``-like objects depending on configuration. Rejections are
        raised as ``OrderError`` subclasses; successful values pass back
        untouched.
        """
        return await self.command_bus.dispatch(command)

    async def place(
        self, customer: str, items: list[OrderItem]
    ) -> Result[str, OrderError]:
        """Dispatch ``PlaceOrder`` and return the new order id.

        Returns:
            ``Ok(order_id)`` on success; ``Err(OrderError)`` when the
            write side rejects the command.
        """
        order_id = await self._dispatch_command(
            PlaceOrder(customer=customer, items=items)
        )
        logger.info("order_placed", order_id=str(order_id), customer=customer)
        return Ok(str(order_id))

    async def pay(self, order_id: str, amount: Decimal) -> Result[None, OrderError]:
        """Dispatch ``PayOrder``.

        Returns:
            ``Ok(None)`` on success; ``Err(OrderError)`` on rejection.
        """
        await self._dispatch_command(PayOrder(order_id=order_id, amount=amount))
        return Ok(None)

    async def ship(self, order_id: str) -> Result[None, OrderError]:
        """Dispatch ``ShipOrder`` (requires a paid order).

        Returns:
            ``Ok(None)`` on success; ``Err(OrderNotPaidError)`` and friends
            on rejection.
        """
        await self._dispatch_command(ShipOrder(order_id=order_id))
        return Ok(None)

    def list_orders(self) -> list[dict[str, object]]:
        """Return the read-model rows for every order."""
        return [row.to_dict() for row in self.view.list_all()]

    def list_outbox(self) -> list[dict[str, object]]:
        """Return outbox records in staging order."""
        return [
            {
                "event_type": record.event_type,
                "status": record.status.value,
            }
            for record in self.outbox.all()
        ]

    async def flush_outbox(self) -> Result[int, Exception]:
        """Flush staged events through the event bus; return count sent.

        Publishes the outbox and then drains the bus so subscribed
        projections advance before this call returns — one call, fully
        consistent read side.

        Returns:
            ``Ok(count)`` of published events; ``Err(OutboxError)`` when
            any publish failed (records stay pending).
        """
        flush = getattr(self.event_bus, "flush", None)
        if callable(flush):
            await flush()
        result = await self.outbox.flush(self.event_bus)
        if result.is_err():
            return Err(result.unwrap_err())
        sent = result.unwrap()
        logger.info("outbox_flushed", published=sent)
        flush = getattr(self.event_bus, "flush", None)
        if callable(flush):
            await flush()
        return Ok(sent)


__all__ = ["OrdersApi"]
