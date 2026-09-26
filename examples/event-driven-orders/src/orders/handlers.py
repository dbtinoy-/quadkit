"""Command handlers for the event-driven orders demo.

Command handlers live on the **write side**: they mutate local state and stage
an outbox record. The outbox relay is the single delivery path to the event
bus; read-side handlers (projection, notifications) react to those events and
never touch command dispatches.

Handler pattern (three steps):

1. Validate preconditions (order exists, correct state).
2. Mutate write-side state (create/update the aggregate).
3. Stage a domain event in the outbox.

Handlers never publish events directly — the outbox ensures at-least-once
delivery and prevents double-publishing.

Convention: one handler per command type; handler class name matches the
command (``PlaceOrder`` -> ``PlaceOrderHandler``).
"""

from __future__ import annotations

from decimal import Decimal

from orders.commands import PayOrder, PlaceOrder, ShipOrder
from orders.domain import (
    Order,
    OrderAlreadyPaidError,
    OrderAlreadyShippedError,
    OrderNotFoundError,
    OrderNotPaidError,
    OrderPaid,
    OrderPlaced,
    OrderShipped,
    OrderStatus,
    order_event,
)
from orders.repository.order_repository import OrderRepository
from orders.repository.outbox import Outbox
from quadkit.contracts.domain import DomainEvent
from quadkit.logging import get_logger

logger = get_logger(__name__)


class OrderCommandHandlerBase:
    """Shared wiring for write-side command handlers.

    Convention: base class holds the repository and outbox so every
    handler subclass inherits the same dependencies.

    Args:
        repository: The write-side repository.
        outbox: The outbox each event is staged in before publishing.
    """

    def __init__(self, repository: OrderRepository, outbox: Outbox) -> None:
        self.repository = repository
        self.outbox = outbox

    async def _publish(self, event: DomainEvent, event_name: str) -> None:
        """Stage an event in the outbox; the relay delivers it later.

        The write side never touches the event bus directly — the outbox
        flush is the single delivery path, so a flushed outbox cannot
        double-deliver events that commands already announced.

        Args:
            event: The domain event to stage.
            event_name: Event type name used in staging logs.
        """
        self.outbox.stage(event)
        logger.debug("order_event_staged", event_type=event_name)


class PlaceOrderHandler(OrderCommandHandlerBase):
    """Handle :class:`PlaceOrder` by persisting the order and staging the event."""

    async def handle(self, command: PlaceOrder) -> str:
        """Persist a new order and stage ``OrderPlaced``.

        Returns:
            The new order identifier.
        """
        total = sum((item.line_total for item in command.items), Decimal("0"))
        order = Order(
            order_id=self.repository.next_id(),
            customer=command.customer,
            total=total,
            status=OrderStatus.PLACED,
        )
        self.repository.save(order)

        event = order_event(
            OrderPlaced,
            order_id=order.order_id,
            customer=order.customer,
            total=total,
        )
        await self._publish(event, "OrderPlaced")
        logger.info("order_placed", order_id=order.order_id, total=str(total))
        return order.order_id


class PayOrderHandler(OrderCommandHandlerBase):
    """Handle :class:`PayOrder` by marking the order paid."""

    async def handle(self, command: PayOrder) -> None:
        """Mark an order as paid and stage ``OrderPaid``.

        Raises:
            OrderNotFoundError: If the order does not exist.
            OrderAlreadyPaidError: If the order is already paid.
            OrderAlreadyShippedError: If the order is already shipped.
        """
        order = self.repository.get(command.order_id)
        if order is None:
            raise OrderNotFoundError(f"Order {command.order_id} not found")
        if order.status is OrderStatus.PAID:
            raise OrderAlreadyPaidError(f"Order {command.order_id} is already paid")
        if order.status is OrderStatus.SHIPPED:
            raise OrderAlreadyShippedError(
                f"Order {command.order_id} is already shipped"
            )

        paid = Order(
            order_id=order.order_id,
            customer=order.customer,
            total=order.total,
            status=OrderStatus.PAID,
        )
        self.repository.save(paid)

        event = order_event(
            OrderPaid,
            order_id=order.order_id,
            amount=command.amount,
        )
        await self._publish(event, "OrderPaid")
        logger.info("order_paid", order_id=order.order_id, amount=str(command.amount))


class ShipOrderHandler(OrderCommandHandlerBase):
    """Handle :class:`ShipOrder` by marking the order shipped."""

    async def handle(self, command: ShipOrder) -> None:
        """Mark an order as shipped and stage ``OrderShipped``.

        Raises:
            OrderNotFoundError: If the order does not exist.
            OrderNotPaidError: If the order has not been paid yet.
        """
        order = self.repository.get(command.order_id)
        if order is None:
            raise OrderNotFoundError(f"Order {command.order_id} not found")
        if order.status is not OrderStatus.PAID:
            raise OrderNotPaidError(
                f"Order {command.order_id} must be paid before shipping"
            )

        shipped = Order(
            order_id=order.order_id,
            customer=order.customer,
            total=order.total,
            status=OrderStatus.SHIPPED,
        )
        self.repository.save(shipped)

        event = order_event(OrderShipped, order_id=order.order_id)
        await self._publish(event, "OrderShipped")
        logger.info("order_shipped", order_id=order.order_id)


__all__ = [
    "OrderCommandHandlerBase",
    "PayOrderHandler",
    "PlaceOrderHandler",
    "ShipOrderHandler",
]
