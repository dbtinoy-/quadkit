"""Public contract for the catalog module.

Convention followed: **Protocol export pattern** — other modules (and the
composition root) import from here only, never from
``storefront.modules.catalog.services``. The ``orders`` module depends on
``ProductCatalogProtocol``, resolved via the DI container, so swapping the
catalog's implementation (a real database, a remote pricing service, ...)
never touches ``orders`` code.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from storefront.modules.catalog.domain import Product


@runtime_checkable
class ProductCatalogProtocol(Protocol):
    """Contract exposed by the catalog module.

    ``orders`` imports ``CatalogModule`` and depends on this protocol —
    never on ``ProductCatalogService`` directly — so the module boundary
    (``@module(exports=[ProductCatalogProtocol])``) is the only visible
    surface between the two bounded contexts.
    """

    async def get(self, sku: str) -> Product | None:
        """Return the product for ``sku``, or ``None`` if unknown."""
        ...

    async def list_all(self) -> list[Product]:
        """Return every product in catalog order."""
        ...

    async def reserve_stock(self, sku: str, qty: int) -> bool:
        """Decrement stock for ``sku`` by ``qty`` if enough is available.

        Returns:
            ``True`` if stock was reserved, ``False`` if insufficient.
        """
        ...


__all__ = ["ProductCatalogProtocol"]
