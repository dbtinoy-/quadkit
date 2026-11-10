"""CLI health checks for quadkit-workflow."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from quadkit.contracts.core.di import ContainerResolverProtocol


async def check_workflow_engine(
    container: ContainerResolverProtocol,
) -> dict[str, object]:
    """Verify workflow engine is operational.

    Args:
        container: Booted DI container.

    Returns:
        A HealthCheckResult-compatible dict.
    """
    return {
        "status": "ok",
        "message": "Workflow engine health check not yet implemented",
    }
