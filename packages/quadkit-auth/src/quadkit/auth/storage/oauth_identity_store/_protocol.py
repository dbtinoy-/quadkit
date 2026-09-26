"""OAuth identity store protocol and identity model."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable


@runtime_checkable
class OAuthIdentityStore(Protocol):
    """Protocol for OAuth identity storage.

    OAuthIdentityStore manages the linking between local user accounts and
    external OAuth2 identity providers. This enables users to authenticate
    using social login while maintaining a consistent local user identity.

    Example:
        Using OAuth identity store::

            store = await container.resolve(OAuthIdentityStore)

            # Link OAuth identity to user
            identity = await store.create_oauth_identity(
                user_id="user-123",
                provider="google",
                provider_user_id="google-456"
            )

            # Find user by OAuth identity
            identity = await store.get_oauth_identity("google", "google-456")
            if identity:
                user = await store.get_user_by_oauth_identity(identity.id)
    """

    async def create_oauth_identity(
        self,
        user_id: str,
        provider: str,
        provider_user_id: str,
    ) -> OAuthIdentity:
        """Create an OAuth identity link for a user.

        Args:
            user_id: The local user ID to link the OAuth identity to.
            provider: The OAuth provider name (e.g., "google", "github").
            provider_user_id: The user's ID at the OAuth provider.

        Returns:
            The created OAuthIdentity instance.
        """
        ...

    async def get_oauth_identity(
        self,
        provider: str,
        provider_user_id: str,
    ) -> OAuthIdentity | None:
        """Get OAuth identity by provider and provider user ID.

        Args:
            provider: The OAuth provider name.
            provider_user_id: The user's ID at the OAuth provider.

        Returns:
            The OAuthIdentity if found, None otherwise.
        """
        ...

    async def get_oauth_identities_for_user(
        self,
        user_id: str,
    ) -> list[OAuthIdentity]:
        """Get all OAuth identities for a user"""
        ...

    async def delete_oauth_identity(
        self,
        provider: str,
        provider_user_id: str,
    ) -> bool:
        """Delete OAuth identity"""
        ...

    async def delete_oauth_identities_for_user(self, user_id: str) -> int:
        """Delete all OAuth identities for a user"""
        ...

    async def get_user_by_oauth_identity(
        self,
        provider: str,
        provider_user_id: str,
    ) -> str | None:
        """Get local user_id by OAuth provider and external user ID.

        This is the key method for resolving OAuth external IDs to local user IDs.
        Used when OAuth tokens contain non-UUID user identifiers (like Google's sub claim).

        Args:
            provider: The OAuth provider name (e.g., "google", "github", "apple").
            provider_user_id: The user's ID at the OAuth provider.

        Returns:
            The local user_id if found, None otherwise.
        """
        ...

    async def resolve_user_id(
        self,
        user_id_or_oauth_id: str,
        provider: str = "google",
    ) -> str | None:
        """Resolve a user_id that may be either a UUID or an OAuth external ID.

        This method handles the common issue where OAuth providers (like Google)
        use non-UUID identifiers (e.g., "101158382316025899191") which cannot
        be used directly in database queries expecting UUIDs.

        Resolution logic:
        1. If user_id_or_oauth_id is a valid UUID format, check if user exists
        2. If not a valid UUID, treat it as an OAuth provider_user_id and look up

        Args:
            user_id_or_oauth_id: Either a local user UUID or an OAuth provider's external ID.
            provider: The OAuth provider to search in (default: "google").

        Returns:
            The resolved local user_id if found, None otherwise.
        """
        ...


class OAuthIdentity:
    """OAuth identity linking user to provider"""

    def __init__(
        self,
        user_id: str,
        provider: str,
        provider_user_id: str,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ):
        self.user_id = user_id
        self.provider = provider
        self.provider_user_id = provider_user_id
        self.created_at = created_at
        self.updated_at = updated_at
