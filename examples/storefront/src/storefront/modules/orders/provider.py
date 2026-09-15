"""DI provider for the orders module.

Convention followed: **Provider pattern** (mirrors
``examples/resilient-rates/src/rates/di/provider.py``) — ``register()``
declares class bindings so the keys exist; ``boot()`` resolves the
cross-module dependency and rebinds the concrete instance via
``container.bind()``.

Resolving ``ProductCatalogProtocol`` in :meth:`boot` — rather than the
concrete ``ProductCatalogService`` — is only possible because
``OrdersModule.configure()`` declares ``imports=[CatalogModule.configure()]``.
Remove that import and this call raises ``ModuleVisibilityError``, naming
this module as the one missing the import.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from quadkit.contracts.core.health import (
    HealthCheckCategory,
    HealthCheckResult,
    HealthStatus,
)
from quadkit.di.provider import Provider
from storefront.modules.catalog.protocols import ProductCatalogProtocol
from storefront.modules.orders.controllers import OrdersApiController
from storefront.modules.orders.protocols import OrderServiceProtocol
from storefront.modules.orders.services import OrderService

if TYPE_CHECKING:
    from quadkit.contracts.core.di import (
        ContainerRegistrarProtocol,
        ContainerResolverProtocol,
    )

__all__ = ["OrdersProvider"]


class OrdersProvider(Provider):
    """Bind the orders service as a container-managed singleton."""

    name = "orders"

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        """Declare bindings; the concrete instance is built in :meth:`boot`.

        ``OrderService`` cannot be built here: it needs the catalog, and
        cross-module resolution is only valid once every provider has
        registered (i.e. after freeze, in ``boot()``).
        """
        container.singleton(OrderService, OrderService)
        container.singleton(OrderServiceProtocol, OrderService)
        container.singleton(OrdersApiController, OrdersApiController)

    async def boot(self, container: ContainerResolverProtocol) -> None:
        """Resolve the catalog, build the service, and rebind the controller.

        This is the cross-module resolution the whole demo exists to show:
        ``ProductCatalogProtocol`` resolves here because ``OrdersModule``
        imports ``CatalogModule``; ``ProductCatalogService`` itself is
        never imported by this module at all.
        """
        catalog = await container.resolve(ProductCatalogProtocol)
        service = OrderService(catalog=catalog)
        container.bind(OrderService, service)
        container.bind(OrderServiceProtocol, service)
        container.bind(OrdersApiController, OrdersApiController(orders=service))

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Report readiness of the orders module."""
        return HealthCheckResult(
            component=self.name,
            status=HealthStatus.HEALTHY,
            category=HealthCheckCategory.READINESS,
        )
