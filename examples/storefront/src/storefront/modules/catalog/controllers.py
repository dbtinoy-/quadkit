"""Convention followed: **Controller pattern** — stateless HTTP adapters
resolved by the router from the container; domain data crosses as
protocol-typed values, never as the module's private service class.

Read-only REST surface for the catalog module.
"""

from __future__ import annotations

from quadkit.web import Controller, get
from storefront.modules.catalog.protocols import ProductCatalogProtocol


class CatalogApiController(Controller):
    """Expose the product catalog for browsing.

    Depends on ``ProductCatalogProtocol`` — the module's exported contract
    — rather than ``ProductCatalogService`` directly, exactly as an
    external module would.
    """

    prefix = "/api/catalog"

    def __init__(self, catalog: ProductCatalogProtocol) -> None:
        self.catalog = catalog

    @get("/products")
    async def list_products(self) -> list[dict[str, object]]:
        """Return every product in the catalog."""
        products = await self.catalog.list_all()
        return [p.to_payload() for p in products]

    @get("/products/{sku}")
    async def get_product(self, sku: str) -> dict[str, object]:
        """Return one product, or a not-found payload."""
        product = await self.catalog.get(sku)
        if product is None:
            return {"error": "not_found", "sku": sku}
        return product.to_payload()


__all__ = ["CatalogApiController"]
