"""Unit tests for the catalog and orders services — no DI container.

These exercise the plain Python classes directly, the same way
``examples/resilient-rates/tests/test_provider.py`` tests
``SimulatedRatesProvider`` in isolation. Cross-module wiring through the
container is covered separately in ``test_module.py``.
"""

from __future__ import annotations

import asyncio
from decimal import Decimal

import pytest

from storefront.modules.catalog.domain import Product
from storefront.modules.catalog.services import ProductCatalogService
from storefront.modules.orders.exceptions import (
    InsufficientStockError,
    UnknownProductError,
)
from storefront.modules.orders.services import OrderService


# --- ProductCatalogService -------------------------------------------------


async def test_seeded_catalog_lists_products() -> None:
    catalog = ProductCatalogService(seed_products=True)

    products = await catalog.list_all()

    assert len(products) == 4
    assert {p.sku for p in products} == {"MUG-001", "TEE-001", "CAP-001", "STK-001"}


async def test_get_unknown_sku_returns_none() -> None:
    catalog = ProductCatalogService(seed_products=True)

    assert await catalog.get("NOPE") is None


async def test_reserve_stock_decrements_and_rejects_when_insufficient() -> None:
    catalog = ProductCatalogService(seed_products=False)
    catalog.seed([Product(sku="X-1", name="Widget", unit_price=Decimal("1.00"), stock=2)])

    assert await catalog.reserve_stock("X-1", 2) is True
    product = await catalog.get("X-1")
    assert product is not None
    assert product.stock == 0

    assert await catalog.reserve_stock("X-1", 1) is False


async def test_reserve_stock_unknown_sku_returns_false() -> None:
    catalog = ProductCatalogService(seed_products=False)

    assert await catalog.reserve_stock("NOPE", 1) is False


async def test_concurrent_reservations_never_oversell() -> None:
    """Ten concurrent reservations for 1 unit each against 5 in stock must
    leave exactly 5 succeed and 5 fail — the per-SKU lock in
    ``reserve_stock`` prevents the classic stampede oversell bug.
    """
    catalog = ProductCatalogService(seed_products=False)
    catalog.seed([Product(sku="X-1", name="Widget", unit_price=Decimal("1.00"), stock=5)])

    results = await asyncio.gather(*[catalog.reserve_stock("X-1", 1) for _ in range(10)])

    assert sum(1 for r in results if r) == 5
    product = await catalog.get("X-1")
    assert product is not None
    assert product.stock == 0


# --- OrderService -----------------------------------------------------------


class _FakeCatalog:
    """Minimal ``ProductCatalogProtocol`` stand-in for isolated OrderService tests."""

    def __init__(self, products: dict[str, Product]) -> None:
        self._products = products

    async def get(self, sku: str) -> Product | None:
        return self._products.get(sku)

    async def list_all(self) -> list[Product]:
        return list(self._products.values())

    async def reserve_stock(self, sku: str, qty: int) -> bool:
        product = self._products.get(sku)
        if product is None or product.stock < qty:
            return False
        self._products[sku] = Product(
            sku=product.sku, name=product.name, unit_price=product.unit_price,
            stock=product.stock - qty,
        )
        return True


def _catalog_with(*products: Product) -> _FakeCatalog:
    return _FakeCatalog({p.sku: p for p in products})


async def test_place_order_prices_lines_from_catalog() -> None:
    catalog = _catalog_with(
        Product(sku="A", name="Alpha", unit_price=Decimal("10.00"), stock=5)
    )
    orders = OrderService(catalog=catalog)

    order = await orders.place_order("Sam", [("A", 2)])

    assert order.total == Decimal("20.00")
    assert order.order_id.startswith("ORD-")


async def test_place_order_unknown_product_raises() -> None:
    orders = OrderService(catalog=_catalog_with())

    with pytest.raises(UnknownProductError):
        await orders.place_order("Sam", [("NOPE", 1)])


async def test_place_order_insufficient_stock_raises() -> None:
    catalog = _catalog_with(
        Product(sku="A", name="Alpha", unit_price=Decimal("10.00"), stock=1)
    )
    orders = OrderService(catalog=catalog)

    with pytest.raises(InsufficientStockError):
        await orders.place_order("Sam", [("A", 2)])


async def test_get_and_list_orders_round_trip() -> None:
    catalog = _catalog_with(
        Product(sku="A", name="Alpha", unit_price=Decimal("10.00"), stock=5)
    )
    orders = OrderService(catalog=catalog)
    placed = await orders.place_order("Sam", [("A", 1)])

    fetched = await orders.get(placed.order_id)
    assert fetched == placed
    assert await orders.list_all() == [placed]
    assert await orders.get("missing") is None
