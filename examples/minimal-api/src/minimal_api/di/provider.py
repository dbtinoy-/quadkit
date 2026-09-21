"""Convention followed: **Provider lifecycle** — ``register()`` declares
singletons (including the controller, as a class binding), ``boot()``
builds the wired controller instance and rebinds it, ``health_check()``
reports readiness; ``config_key``/``config_model`` wire the typed yaml
section into ``self.config``.

Lifecycle wiring for the Minimal API demo: the typed config model is the
only dependency, and the controller reads yaml/env-driven settings
through it.
"""

from __future__ import annotations

from minimal_api.config import MinimalApiConfig
from minimal_api.controllers.api import HelloController
from quadkit.contracts.core import HealthCheckResult, HealthStatus
from quadkit.contracts.core.di import (
    ContainerRegistrarProtocol,
    ContainerResolverProtocol,
)
from quadkit.di.provider import Provider


class MinimalApiProvider(Provider):
    """Bind the demo's typed config and its controller."""

    name = "minimal_api"
    config_key: str | None = "minimal_api"
    config_model: type | None = MinimalApiConfig

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        config = (
            self.config
            if isinstance(self.config, MinimalApiConfig)
            else MinimalApiConfig()
        )
        container.singleton(MinimalApiConfig, config)
        container.singleton(HelloController, HelloController)

    async def boot(self, container: ContainerResolverProtocol) -> None:
        config = await container.resolve(MinimalApiConfig)
        container.bind(HelloController, HelloController(config))

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Report provider wiring for framework health aggregation."""
        config = (
            self.config
            if isinstance(self.config, MinimalApiConfig)
            else MinimalApiConfig()
        )
        return HealthCheckResult(
            component=self.name,
            status=HealthStatus.HEALTHY,
            details={"demo": "minimal-api", "greeting": config.greeting},
        )


__all__ = ["MinimalApiProvider"]
