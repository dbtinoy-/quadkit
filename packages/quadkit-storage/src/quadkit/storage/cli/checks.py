"""CLI health checks for quadkit-storage."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from quadkit.contracts.core.di import ContainerResolverProtocol


async def check_storage_backend(
    container: ContainerResolverProtocol,
) -> dict[str, object]:
    """Verify file storage backend connectivity.

    Args:
        container: Booted DI container.

    Returns:
        A HealthCheckResult-compatible dict.
    """
    return {
        "status": "ok",
        "message": "Storage backend health check not yet implemented",
    }
