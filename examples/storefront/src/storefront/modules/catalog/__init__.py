"""catalog module — bounded context boundary.

Convention followed: **Module boundary pattern** (Pattern 3, "Modular App
Layout" — see ``docs/getting-started/project-structure.md``). ``__init__.py``
is the module's public API: the ``@module`` class declaration plus the
``configure()``/``stub()`` factories other bounded contexts and the
composition root use to wire it in.

The catalog module owns product data and pricing. It exports only
``ProductCatalogProtocol`` — the ``orders`` module (and anything else that
needs prices) imports this module and resolves the protocol; it never
imports ``storefront.modules.catalog.services`` directly. That is the whole
point of the boundary: swap the catalog's storage or pricing rules and
every consumer keeps working unchanged.
"""

from __future__ import annotations

from quadkit.di.module import DynamicModule, Module, module
from storefront.modules.catalog.protocols import ProductCatalogProtocol


@module()
class CatalogModule(Module):
    """Bounded context: product catalog and pricing.

    ``quadkit gen <component> <name> --module catalog`` would write
    module-local components (controllers, services, repositories, ...)
    into this package in a CLI-scaffolded project; here the components are
    hand-written to keep the demo runnable without the CLI installed.
    """

    @classmethod
    def configure(cls, seed_products: bool = True) -> DynamicModule:
        """Wire the catalog module.

        Args:
            seed_products: Seed the in-memory catalog with demo products.
                Defaults to ``True``; set ``False`` for tests that seed
                their own fixtures.

        Returns:
            A :class:`~quadkit.di.module.DynamicModule` descriptor.
        """
        from storefront.modules.catalog.provider import CatalogProvider

        return DynamicModule(
            module=cls,
            providers=[CatalogProvider(seed_products=seed_products)],
            exports=[ProductCatalogProtocol],
        )

    @classmethod
    def stub(cls) -> DynamicModule:
        """Return a no-seed CatalogModule for tests that own their fixtures."""
        return cls.configure(seed_products=False)


__all__ = ["CatalogModule"]
