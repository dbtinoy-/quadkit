"""CLI health checks for quadkit-cache."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from quadkit.contracts.core.di import ContainerResolverProtocol


async def check_cache_connection(
    container: ContainerResolverProtocol,
) -> dict[str, object]:
    """Verify cache backend connectivity.

    Args:
        container: Booted DI container.

    Returns:
        A HealthCheckResult-compatible dict.
    """
    return {"status": "ok", "message": "Cache health check not yet implemented"}
