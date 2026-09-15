"""Core providers for Quadkit Applications.

Contains ``CoreProvider``, the main aggregating provider that bundles all
framework sub-providers into a single unit for easy bootstrapping.
"""

from __future__ import annotations

from quadkit.contracts.core import HealthCheckResult
from quadkit.contracts.core.di import (
    ContainerRegistrarProtocol,
    ContainerResolverProtocol,
)
from quadkit.di.provider import Provider, ProviderPriority
from quadkit.logging import get_logger

logger = get_logger(__name__)


class CoreProvider(Provider):
    """Main **aggregating** provider for Quadkit core services.

    ``CoreProvider`` is the single entry point for application bootstrap.
    It does **not** register services directly — instead it relies on the
    orchestrator to discover and execute all framework sub-providers in
    dependency order.

    **Do NOT confuse with** :class:`~quadkit.primitives.di.provider.CoreInfrastructureProvider`:

    +-----------------------------------+----------------------------------------------------+
    | ``CoreProvider``                  | ``CoreInfrastructureProvider``                     |
    +===================================+====================================================+
    | Aggregating, no registrations     | Leaf provider, registers concrete primitives       |
    +-----------------------------------+----------------------------------------------------+
    | Used by application bootstrap     | Used inside the framework internals                |
    +-----------------------------------+----------------------------------------------------+
    | ``name = "core"``                 | ``name = "common"``                                |
    +-----------------------------------+----------------------------------------------------+
    """

    name = "core"
    priority = ProviderPriority.INFRASTRUCTURE

    def __init__(self) -> None:
        """Initialize CoreProvider."""
        super().__init__()

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        """Register core services.

        Note: Sub-providers are now handled by the orchestrator via
        the sub_providers property and recursive discovery.
        """

    async def boot(self, container: ContainerResolverProtocol) -> None:
        """Boot core services."""

    async def shutdown(self) -> None:
        """Shutdown core services."""

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """CoreProvider itself is always healthy if it reached boot.

        Individual core services (config, logging, etc.) are checked
        by their own providers via the orchestrator.
        """
        from quadkit.contracts.core import HealthCheckResult, HealthStatus

        return HealthCheckResult(
            component=self.name,
            status=HealthStatus.HEALTHY,
        )


__all__ = [
    "CoreProvider",
]
