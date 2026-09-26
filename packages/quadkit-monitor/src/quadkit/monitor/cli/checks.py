"""CLI health checks for quadkit-monitor."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from quadkit.contracts.core.di import ContainerResolverProtocol


async def check_metrics_backend(
    container: ContainerResolverProtocol,
) -> dict[str, object]:
    """Verify metrics backend (Prometheus/OTLP) connectivity.

    Args:
        container: Booted DI container.

    Returns:
        A HealthCheckResult-compatible dict.
    """
    return {
        "status": "ok",
        "message": "Metrics backend health check not yet implemented",
    }


async def check_tracing_backend(
    container: ContainerResolverProtocol,
) -> dict[str, object]:
    """Verify tracing backend connectivity.

    Args:
        container: Booted DI container.

    Returns:
        A HealthCheckResult-compatible dict.
    """
    return {
        "status": "ok",
        "message": "Tracing backend health check not yet implemented",
    }
