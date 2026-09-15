"""orders module — bounded context boundary.

Convention followed: **Module boundary pattern** — see
``storefront.modules.catalog`` for the mirror-image explanation. This
module's ``@module(imports=[CatalogModule])`` declaration is the load-bearing
line of the whole demo: it is what makes ``ProductCatalogProtocol`` visible
inside ``orders`` and nowhere else that did not also import ``CatalogModule``.

Try removing the ``imports=[CatalogModule]`` line and running the demo —
boot fails with ``ModuleVisibilityError`` naming the missing import, not a
generic ``NameError`` or ``KeyError``. That failure mode is the module
system doing its job: visibility is enforced at compile time, not
discovered at a random runtime call site.
"""

from __future__ import annotations

from quadkit.di.module import DynamicModule, Module, module
from storefront.modules.catalog import CatalogModule
from storefront.modules.orders.protocols import OrderServiceProtocol


@module()
class OrdersModule(Module):
    """Bounded context: order placement, backed by the catalog for pricing."""

    @classmethod
    def configure(cls, catalog: DynamicModule | None = None) -> DynamicModule:
        """Wire the orders module.

        Imports :class:`CatalogModule` so ``OrdersProvider.boot()`` can
        resolve ``ProductCatalogProtocol`` — the DI container enforces
        this import at compile time via
        :class:`~quadkit.di.module.compiler.compiler.ModuleCompiler`.

        Args:
            catalog: An already-configured ``CatalogModule`` DynamicModule
                to import. Pass the same instance used elsewhere in the
                module graph (e.g. ``storefront.modules.MODULES``) — the
                compiler rejects two independent ``configure()`` calls for
                the same module class as a duplicate configuration. When
                omitted, a fresh default-configured ``CatalogModule`` is
                created (fine for standalone use, e.g. in tests).

        Returns:
            A :class:`~quadkit.di.module.DynamicModule` descriptor.
        """
        from storefront.modules.orders.provider import OrdersProvider

        return DynamicModule(
            module=cls,
            providers=[OrdersProvider()],
            imports=[catalog or CatalogModule.configure()],
            exports=[OrderServiceProtocol],
        )

    @classmethod
    def stub(cls) -> DynamicModule:
        """Return an OrdersModule wired to a no-seed CatalogModule."""
        from storefront.modules.orders.provider import OrdersProvider

        return DynamicModule(
            module=cls,
            providers=[OrdersProvider()],
            imports=[CatalogModule.stub()],
            exports=[OrderServiceProtocol],
        )


__all__ = ["OrdersModule"]
