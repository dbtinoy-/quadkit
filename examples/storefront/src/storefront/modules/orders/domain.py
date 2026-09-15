"""Domain model for the orders module.

Convention followed: **Value type** — frozen dataclasses with a
``to_payload`` serializer, matching ``storefront.modules.catalog.domain``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass(frozen=True)
class OrderLine:
    """One priced line item, snapshotted at order-placement time.

    Prices are copied from the catalog at placement time rather than
    looked up live on every read — the order is a fact about what the
    customer agreed to pay, independent of later catalog price changes.
    """

    sku: str
    name: str
    qty: int
    unit_price: Decimal

    @property
    def line_total(self) -> Decimal:
        """Return ``qty * unit_price``."""
        return self.unit_price * self.qty

    def to_payload(self) -> dict[str, object]:
        """Return the JSON-safe representation used by the API layer."""
        return {
            "sku": self.sku,
            "name": self.name,
            "qty": self.qty,
            "unit_price": str(self.unit_price),
            "line_total": str(self.line_total),
        }


@dataclass(frozen=True)
class Order:
    """A placed order: an immutable snapshot of priced catalog lines.

    Attributes:
        order_id: Unique identifier assigned at placement.
        customer: Customer name/identifier.
        lines: Priced line items.
    """

    order_id: str
    customer: str
    lines: list[OrderLine] = field(default_factory=list)

    @property
    def total(self) -> Decimal:
        """Return the sum of every line's total."""
        total = Decimal("0")
        for line in self.lines:
            total += line.line_total
        return total

    def to_payload(self) -> dict[str, object]:
        """Return the JSON-safe representation used by the API layer."""
        return {
            "order_id": self.order_id,
            "customer": self.customer,
            "lines": [line.to_payload() for line in self.lines],
            "total": str(self.total),
        }


__all__ = ["Order", "OrderLine"]
