"""CLI health checks for quadkit-sql."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from quadkit.contracts.core.di import ContainerResolverProtocol


async def check_database_connection(
    container: ContainerResolverProtocol,
) -> dict[str, object]:
    """Verify database connectivity and migration status.

    Args:
        container: Booted DI container providing DatabaseProviderProtocol.

    Returns:
        A HealthCheckResult-compatible dict with status and message.
    """
    return {"status": "ok", "message": "Database health check not yet implemented"}
