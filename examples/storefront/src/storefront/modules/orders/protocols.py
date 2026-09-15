"""Public contract for the orders module.

Convention followed: **Protocol export pattern** — mirrors
``storefront.modules.catalog.protocols``. Nothing outside this demo depends
on ``OrderServiceProtocol`` today, but exporting it keeps the module
symmetric with ``catalog`` and is what a third bounded context (billing,
fulfillment, ...) would import if it were added later.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from storefront.modules.orders.domain import Order


@runtime_checkable
class OrderServiceProtocol(Protocol):
    """Contract exposed by the orders module."""

    async def place_order(self, customer: str, items: list[tuple[str, int]]) -> Order:
        """Place an order for ``items`` (sku, qty pairs) and return it."""
        ...

    async def get(self, order_id: str) -> Order | None:
        """Return the order for ``order_id``, or ``None`` if unknown."""
        ...

    async def list_all(self) -> list[Order]:
        """Return every placed order, oldest first."""
        ...


__all__ = ["OrderServiceProtocol"]
