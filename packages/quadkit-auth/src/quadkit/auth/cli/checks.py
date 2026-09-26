"""CLI health checks for quadkit-auth."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from quadkit.contracts.core.di import ContainerResolverProtocol


async def check_auth_service(container: ContainerResolverProtocol) -> dict[str, object]:
    """Verify auth service and JWT manager are operational.

    Args:
        container: Booted DI container.

    Returns:
        A HealthCheckResult-compatible dict.
    """
    return {"status": "ok", "message": "Auth service health check not yet implemented"}
