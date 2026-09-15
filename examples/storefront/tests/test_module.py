"""Integration tests: boot the real composition root and exercise the
cross-module dependency the whole demo exists to demonstrate.

``orders`` resolves ``ProductCatalogProtocol`` — never the concrete
``ProductCatalogService`` — because ``OrdersModule`` imports
``CatalogModule``. A second group of tests proves the module compiler
*enforces* that boundary: remove the import and resolution fails with
``ModuleVisibilityError``, not a silent fallback.
"""

from __future__ import annotations

from typing import AsyncIterator

import pytest

from quadkit.app import Application
from quadkit.contracts.exceptions.provider import ModuleVisibilityError
from quadkit.di.context import (
    check_visibility,
    clear_module_context,
    set_module_context,
)
from quadkit.di.module.compiler import ModuleCompiler
from quadkit.di.module.dynamic import DynamicModule
from storefront.app import create_app
from storefront.modules.catalog import CatalogModule
from storefront.modules.catalog.protocols import ProductCatalogProtocol
from storefront.modules.catalog.services import ProductCatalogService
from storefront.modules.orders import OrdersModule
from storefront.modules.orders.provider import OrdersProvider
from storefront.modules.orders.services import OrderService


@pytest.fixture
async def app() -> AsyncIterator[Application]:
    instance = create_app()
    await instance.start()
    try:
        yield instance
    finally:
        await instance.stop()


class TestCrossModuleResolution:
    """Exercise the real, wired application end-to-end."""

    async def test_orders_resolves_catalog_protocol_not_concrete_class(
        self, app: Application
    ) -> None:
        """The container holds ``ProductCatalogProtocol``; both modules see it."""
        catalog = await app.container.resolve(ProductCatalogProtocol)
        assert isinstance(catalog, ProductCatalogService)

    async def test_placing_an_order_reserves_catalog_stock(
        self, app: Application
    ) -> None:
        """Placing an order through ``orders`` decrements ``catalog`` stock —
        proof the two bounded contexts are actually wired together, not
        just independently bootable.
        """
        catalog = await app.container.resolve(ProductCatalogProtocol)
        before = await catalog.get("MUG-001")
        assert before is not None

        orders = await app.container.resolve(OrderService)
        await orders.place_order("Test Customer", [("MUG-001", 3)])

        after = await catalog.get("MUG-001")
        assert after is not None
        assert after.stock == before.stock - 3


class TestModuleVisibilityEnforcement:
    """Prove the module boundary is enforced by the compiler, not convention."""

    def test_orders_import_makes_catalog_protocol_visible(self) -> None:
        """With the real ``imports=[CatalogModule.configure()]`` declaration,
        ``OrdersModule`` can see ``ProductCatalogProtocol``.
        """
        graph = ModuleCompiler().compile([OrdersModule.configure()])
        tokens = set_module_context(OrdersModule, graph)
        try:
            assert check_visibility(ProductCatalogProtocol) is True
        finally:
            clear_module_context(tokens)

    def test_removing_the_import_breaks_visibility(self) -> None:
        """Without the import, ``OrdersModule`` cannot see the catalog's
        protocol — this is what ``ModuleVisibilityError`` protects against.
        """
        broken_orders = DynamicModule(
            module=OrdersModule,
            providers=[OrdersProvider()],
            imports=[],  # the load-bearing line, deliberately omitted
        )
        graph = ModuleCompiler().compile([CatalogModule.configure(), broken_orders])
        tokens = set_module_context(OrdersModule, graph)
        try:
            assert check_visibility(ProductCatalogProtocol) is False
        finally:
            clear_module_context(tokens)

    async def test_broken_orders_raises_module_visibility_error_at_boot(self) -> None:
        """End-to-end: booting the broken graph raises ``ModuleVisibilityError``
        naming the missing import, not a generic ``NameError``/``KeyError``.
        """
        broken_orders = DynamicModule(
            module=OrdersModule,
            providers=[OrdersProvider()],
            imports=[],
        )
        broken_app = Application(name="broken-storefront")
        broken_app.add_modules([CatalogModule.configure(), broken_orders])
        with pytest.raises(ModuleVisibilityError):
            await broken_app.start()
        await broken_app.stop()
