from __future__ import annotations

import time
from typing import TYPE_CHECKING

from quadkit.contracts.core import HealthCheckResult, HealthStatus
from quadkit.di.provider import Provider, ProviderPriority
from quadkit.mapping.core.mapper import MappingRegistry, ObjectMapperImpl

if TYPE_CHECKING:
    from quadkit.contracts.core.di import (
        ContainerRegistrarProtocol,
        ContainerResolverProtocol,
    )


class MappingProvider(Provider):
    """Registers the MappingRegistry and ObjectMapperImpl singletons."""

    name = "mapping"
    priority = ProviderPriority.INFRASTRUCTURE

    def __init__(self) -> None:
        super().__init__()
        self._mapper: ObjectMapperImpl | None = None

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        """Register MappingRegistry and ObjectMapperImpl into *container*."""
        registry = MappingRegistry()
        mapper = ObjectMapperImpl(registry)
        self._mapper = mapper
        container.singleton(MappingRegistry, registry)
        container.singleton(ObjectMapperImpl, mapper)

    async def boot(self, container: ContainerResolverProtocol) -> None:
        """No boot-time work required for the mapping module."""

    async def shutdown(self) -> None:
        """No resources to release for the mapping module."""

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Check provider health.

        Args:
            timeout: Maximum seconds to wait for health check response.

        Returns:
            HealthCheckResult with status and component details.
        """

        start = time.perf_counter()

        if self._mapper is None:
            return HealthCheckResult(
                component="mapping",
                status=HealthStatus.DEGRADED,
                message="object mapper not initialized",
                duration_ms=(time.perf_counter() - start) * 1000,
            )

        return HealthCheckResult(
            component="mapping",
            status=HealthStatus.HEALTHY,
            details={"components": {"mapper": {"status": "healthy"}}},
            duration_ms=(time.perf_counter() - start) * 1000,
        )


__all__ = ["MappingProvider"]
