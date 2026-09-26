"""CLI shell context factories for quadkit-monitor."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from quadkit.contracts.observability.metrics import MetricsBackendProtocol

if TYPE_CHECKING:
    from quadkit.contracts.core.di import ContainerResolverProtocol


async def provide_metrics(
    container: ContainerResolverProtocol,
) -> MetricsBackendProtocol:
    """Provide metrics backend for interactive shell use.

    Args:
        container: Booted DI container.

    Returns:
        The resolved metrics backend instance.
    """
    return cast(
        "MetricsBackendProtocol", await container.resolve(MetricsBackendProtocol)
    )
