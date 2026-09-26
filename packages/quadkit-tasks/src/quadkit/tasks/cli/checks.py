"""CLI health checks for quadkit-tasks."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from quadkit.contracts.core.di import ContainerResolverProtocol


async def check_task_worker(container: ContainerResolverProtocol) -> dict[str, object]:
    """Check task worker process is responsive.

    Args:
        container: Booted DI container.

    Returns:
        A HealthCheckResult-compatible dict.
    """
    return {"status": "ok", "message": "Task worker health check not yet implemented"}
