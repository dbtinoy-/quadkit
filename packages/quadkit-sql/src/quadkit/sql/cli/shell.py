"""CLI shell context factories for quadkit-sql."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from quadkit.contracts.data.sql.database import DatabaseProviderProtocol

if TYPE_CHECKING:
    from quadkit.contracts.core.di import ContainerResolverProtocol


async def provide_db(container: ContainerResolverProtocol) -> DatabaseProviderProtocol:
    """Provide database provider for interactive shell queries.

    Args:
        container: Booted DI container.

    Returns:
        The resolved DatabaseProviderProtocol instance.
    """
    return cast(
        "DatabaseProviderProtocol",
        await container.resolve(DatabaseProviderProtocol),
    )


async def provide_migration(container: ContainerResolverProtocol) -> object:
    """Provide migration runner for interactive shell use.

    Args:
        container: Booted DI container.

    Returns:
        The resolved migration runner or None if not available.
    """
    return None
