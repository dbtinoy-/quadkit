"""Convention followed: **Provider lifecycle** — ``register()`` declares
singletons (including the controller, as a class binding), ``boot()``
resolves cross-module contracts and rebinds the wired controller instance,
``health_check()`` reports readiness; ``config_key``/``config_model`` wire
the typed yaml section into ``self.config``.

Lifecycle wiring for the Cache-Aside demo: the cache backend comes from
``quadkit-cache``'s ``CacheModule``; this provider wraps it in stampede
protection and hands it to the report service.
"""

from __future__ import annotations

from cache_side.config import CacheSideConfig
from cache_side.controllers.api import ReportController
from cache_side.services.report import ReportService
from quadkit.cache.service.stampede import StampedeProtectedCache
from quadkit.contracts.core import HealthCheckResult, HealthStatus
from quadkit.contracts.core.di import (
    ContainerRegistrarProtocol,
    ContainerResolverProtocol,
)
from quadkit.contracts.infra.cache import CacheBackendProtocol
from quadkit.di.provider import Provider


class CacheSideProvider(Provider):
    """Resolve the cache backend and bind the report service + controller."""

    name = "cache_side"
    config_key: str | None = "cache_side"
    config_model: type | None = CacheSideConfig

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        config = (
            self.config
            if isinstance(self.config, CacheSideConfig)
            else CacheSideConfig()
        )
        container.singleton(CacheSideConfig, config)
        container.singleton(ReportController, ReportController)

    async def boot(self, container: ContainerResolverProtocol) -> None:
        config = await container.resolve(CacheSideConfig)
        backend = await container.resolve(CacheBackendProtocol)
        protection = StampedeProtectedCache(cache=backend)
        service = ReportService(cache=backend, protection=protection, config=config)
        container.bind(ReportController, ReportController(service=service))

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Report provider wiring for framework health aggregation."""
        return HealthCheckResult(
            component=self.name,
            status=HealthStatus.HEALTHY,
            details={"demo": "cache-aside"},
        )


__all__ = ["CacheSideProvider"]
