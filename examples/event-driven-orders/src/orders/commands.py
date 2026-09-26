"""Commands for the event-driven orders demo.

Commands are frozen dataclasses extending the framework's
:class:`~quadkit.events.messages.Command`. Each command targets a handler on
the command bus; handlers mutate the write-side state and publish domain
events afterwards (CQRS write path).

Commands are **intent objects** — they describe what the caller wants, not how
to do it.  The command bus routes each command type to exactly one handler.

Convention: ``@dataclass(frozen=True, kw_only=True)`` for immutable
command objects; ``Command`` base from quadkit.events.messages.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from orders.domain import OrderItem
from quadkit.events.messages import Command


@dataclass(frozen=True, kw_only=True)
class PlaceOrder(Command):
    """Intent to create a new order.

    Attributes:
        customer: Customer name the order is placed for.
        items: Line items of the order.
    """

    customer: str
    items: list[OrderItem] = field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
class PayOrder(Command):
    """Intent to mark an order as paid.

    Attributes:
        order_id: Identifier of the order to pay.
        amount: Amount to record.
    """

    order_id: str
    amount: Decimal = Decimal("0")


@dataclass(frozen=True, kw_only=True)
class ShipOrder(Command):
    """Intent to mark an order as shipped.

    Attributes:
        order_id: Identifier of the order to ship.
    """

    order_id: str


__all__ = ["PayOrder", "PlaceOrder", "ShipOrder"]
