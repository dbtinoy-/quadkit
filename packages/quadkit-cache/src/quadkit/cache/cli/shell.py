"""CLI shell context factories for quadkit-cache."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from quadkit.contracts.infra.cache.protocols import CacheBackendProtocol

if TYPE_CHECKING:
    from quadkit.contracts.core.di import ContainerResolverProtocol


async def provide_cache(
    container: ContainerResolverProtocol,
) -> CacheBackendProtocol:
    """Provide cache backend for interactive shell use.

    Args:
        container: Booted DI container.

    Returns:
        The resolved CacheBackendProtocol instance.
    """
    return cast(
        "CacheBackendProtocol",
        await container.resolve(CacheBackendProtocol),
    )
