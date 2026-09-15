"""Application services for the orders module.

Convention followed: **Service pattern** — ``OrderService`` is the sole
implementation of ``OrderServiceProtocol``. Its constructor takes
``ProductCatalogProtocol``, never ``ProductCatalogService`` — that is the
whole demonstration. The container resolves the protocol to the concrete
instance registered by ``CatalogProvider`` because ``OrdersModule`` imports
``CatalogModule`` and the protocol is in its export list; if that import
were missing, resolution would fail with ``ModuleVisibilityError`` rather
than silently substituting something else.
"""

from __future__ import annotations

import itertools

from storefront.modules.catalog.protocols import ProductCatalogProtocol
from storefront.modules.orders.domain import Order, OrderLine
from storefront.modules.orders.exceptions import (
    InsufficientStockError,
    UnknownProductError,
)


class OrderService:
    """Places orders by pricing and reserving stock through the catalog."""

    def __init__(self, catalog: ProductCatalogProtocol) -> None:
        # Cross-module dependency — resolved as the protocol, not the
        # concrete `ProductCatalogService`. Swap catalog's storage backend
        # and this line does not change.
        self.catalog = catalog
        self._orders: dict[str, Order] = {}
        self._ids = itertools.count(1)

    async def place_order(self, customer: str, items: list[tuple[str, int]]) -> Order:
        """Place an order for ``items`` (sku, qty pairs) and return it.

        Raises:
            UnknownProductError: A SKU is not in the catalog.
            InsufficientStockError: Not enough stock for a requested SKU.
        """
        lines: list[OrderLine] = []
        for sku, qty in items:
            product = await self.catalog.get(sku)
            if product is None:
                raise UnknownProductError(f"unknown product {sku!r}")
            reserved = await self.catalog.reserve_stock(sku, qty)
            if not reserved:
                raise InsufficientStockError(
                    f"insufficient stock for {sku!r} (requested {qty})"
                )
            lines.append(
                OrderLine(
                    sku=sku, name=product.name, qty=qty, unit_price=product.unit_price
                )
            )

        order_id = f"ORD-{next(self._ids):04d}"
        order = Order(order_id=order_id, customer=customer, lines=lines)
        self._orders[order_id] = order
        return order

    async def get(self, order_id: str) -> Order | None:
        """Return the order for ``order_id``, or ``None`` if unknown."""
        return self._orders.get(order_id)

    async def list_all(self) -> list[Order]:
        """Return every placed order, oldest first."""
        return list(self._orders.values())


__all__ = ["OrderService"]
