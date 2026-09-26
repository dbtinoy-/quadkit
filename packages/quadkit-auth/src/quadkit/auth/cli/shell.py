"""CLI shell context factories for quadkit-auth."""

from __future__ import annotations

from typing import TYPE_CHECKING

from quadkit.auth.authn.services import AuthenticationService

if TYPE_CHECKING:
    from quadkit.contracts.core.di import ContainerResolverProtocol


async def provide_auth(container: ContainerResolverProtocol) -> AuthenticationService:
    """Provide AuthenticationService for interactive shell use.

    Args:
        container: Booted DI container.

    Returns:
        The resolved AuthenticationService instance.
    """
    return await container.resolve(AuthenticationService)
