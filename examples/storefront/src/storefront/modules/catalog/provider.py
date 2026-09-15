"""DI provider for the catalog module.

Convention followed: **Provider pattern** (mirrors
``examples/resilient-rates/src/rates/di/provider.py``) — ``register()``
declares class bindings so the keys exist; ``boot()`` builds the concrete
service and rebinds it via ``container.bind()``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from quadkit.contracts.core.health import (
    HealthCheckCategory,
    HealthCheckResult,
    HealthStatus,
)
from quadkit.di.provider import Provider
from storefront.modules.catalog.controllers import CatalogApiController
from storefront.modules.catalog.protocols import ProductCatalogProtocol
from storefront.modules.catalog.services import ProductCatalogService

if TYPE_CHECKING:
    from quadkit.contracts.core.di import (
        ContainerRegistrarProtocol,
        ContainerResolverProtocol,
    )

__all__ = ["CatalogProvider"]


class CatalogProvider(Provider):
    """Bind the catalog service as a container-managed singleton."""

    name = "catalog"

    def __init__(self, *, seed_products: bool = True) -> None:
        super().__init__()
        self._seed_products = seed_products

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        """Declare bindings; the concrete instance is built in :meth:`boot`."""
        container.singleton(ProductCatalogService, ProductCatalogService)
        # Exported binding: `orders` (and anything else that imports this
        # module) resolves the protocol, never `ProductCatalogService`
        # directly — that class is private to this module.
        container.singleton(ProductCatalogProtocol, ProductCatalogService)
        container.singleton(CatalogApiController, CatalogApiController)

    async def boot(self, container: ContainerResolverProtocol) -> None:
        """Build the catalog singleton and rebind it under both keys."""
        service = ProductCatalogService(seed_products=self._seed_products)
        container.bind(ProductCatalogService, service)
        container.bind(ProductCatalogProtocol, service)
        container.bind(CatalogApiController, CatalogApiController(catalog=service))

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Report readiness of the catalog module."""
        return HealthCheckResult(
            component=self.name,
            status=HealthStatus.HEALTHY,
            category=HealthCheckCategory.READINESS,
        )
