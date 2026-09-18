"""OAuth identity resolution protocols.

Protocols for resolving external OAuth provider IDs to internal user IDs.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class IdentityResolverProtocol(Protocol):
    """Protocol for resolving external OAuth identities to internal user IDs.

    This protocol is used to map OAuth external IDs (like Google's 'sub' claim)
    to internal UUIDs. This is necessary because OAuth providers use their own
    ID format which may not be valid UUIDs.
    """

    async def resolve_user_id(
        self,
        external_id: str,
        provider: str = "google",
    ) -> str | None:
        """Resolve an external OAuth ID to an internal user UUID.

        Args:
            external_id: The external ID from the OAuth provider (e.g., Google's sub claim).
            provider: The OAuth provider name (e.g., "google", "apple").

        Returns:
            The internal user UUID if found, None otherwise.
        """
        ...

    def resolve_user_id_sync(
        self,
        external_id: str,
        provider: str = "google",
    ) -> str | None:
        """Synchronous version of resolve_user_id.

        Args:
            external_id: The external ID from the OAuth provider.
            provider: The OAuth provider name.

        Returns:
            The internal user UUID if found, None otherwise.
        """
        ...


__all__ = ["IdentityResolverProtocol"]
