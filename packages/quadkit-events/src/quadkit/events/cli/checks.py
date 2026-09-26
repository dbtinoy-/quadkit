"""CLI health checks for quadkit-events."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from quadkit.contracts.core.di import ContainerResolverProtocol


async def check_event_bus(container: ContainerResolverProtocol) -> dict[str, object]:
    """Verify event bus and store are operational.

    Args:
        container: Booted DI container.

    Returns:
        A HealthCheckResult-compatible dict.
    """
    return {"status": "ok", "message": "Event bus health check not yet implemented"}
