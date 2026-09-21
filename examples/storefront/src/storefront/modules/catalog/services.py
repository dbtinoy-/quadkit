"""Application services for the catalog module.

Convention followed: **Service pattern** — ``ProductCatalogService`` is the
sole implementation of ``ProductCatalogProtocol``. It is registered as a
container singleton by ``CatalogProvider`` and bound to the protocol, but
the class itself is never imported outside this module — only the
protocol crosses the boundary.
"""

from __future__ import annotations

import asyncio
from decimal import Decimal

from storefront.modules.catalog.domain import Product


def _seed_data() -> dict[str, Product]:
    """Deterministic demo catalog — no external data source."""
    seed = [
        Product(
            sku="MUG-001", name="Quadkit Mug", unit_price=Decimal("12.00"), stock=40
        ),
        Product(
            sku="TEE-001",
            name="Quadkit T-Shirt",
            unit_price=Decimal("24.00"),
            stock=25,
        ),
        Product(
            sku="CAP-001", name="Quadkit Cap", unit_price=Decimal("18.50"), stock=15
        ),
        Product(
            sku="STK-001",
            name="Quadkit Sticker Pack",
            unit_price=Decimal("5.00"),
            stock=3,
        ),
    ]
    return {p.sku: p for p in seed}


class ProductCatalogService:
    """In-memory catalog implementing :class:`ProductCatalogProtocol`.

    A per-SKU :class:`asyncio.Lock` guards ``reserve_stock`` so concurrent
    orders racing for the last units of a SKU never oversell — the same
    single-flight discipline the ``resilient-rates`` demo uses for reads,
    applied here to a write path.
    """

    def __init__(self, *, seed_products: bool = True) -> None:
        self._products: dict[str, Product] = _seed_data() if seed_products else {}
        self._locks: dict[str, asyncio.Lock] = {}

    def _lock_for(self, sku: str) -> asyncio.Lock:
        lock = self._locks.get(sku)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[sku] = lock
        return lock

    def seed(self, products: list[Product]) -> None:
        """Replace the catalog contents (test/demo helper)."""
        self._products = {p.sku: p for p in products}

    async def get(self, sku: str) -> Product | None:
        """Return the product for ``sku``, or ``None`` if unknown."""
        return self._products.get(sku)

    async def list_all(self) -> list[Product]:
        """Return every product, catalog-insertion ordered."""
        return list(self._products.values())

    async def reserve_stock(self, sku: str, qty: int) -> bool:
        """Decrement stock for ``sku`` by ``qty`` if enough is available."""
        async with self._lock_for(sku):
            product = self._products.get(sku)
            if product is None or product.stock < qty:
                return False
            self._products[sku] = Product(
                sku=product.sku,
                name=product.name,
                unit_price=product.unit_price,
                stock=product.stock - qty,
            )
            return True


__all__ = ["ProductCatalogService"]
