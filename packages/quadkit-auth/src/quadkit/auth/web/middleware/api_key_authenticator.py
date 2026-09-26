"""API key authentication component."""

from __future__ import annotations

from typing import Any

from quadkit.contracts import AuthProviderProtocol


class ApiKeyAuthenticator:
    """Handles API key validation and user resolution."""

    def __init__(self, auth_provider: AuthProviderProtocol):
        self.auth_provider = auth_provider

    async def authenticate(self, token: str, request: Any) -> Any:
        """Validate API key and return user if valid."""
        if not token.startswith("sk_"):
            return None

        if not self.auth_provider.api_key_manager:
            return None

        api_key = await self.auth_provider.api_key_manager.validate_key(
            token,
            ip_address=getattr(request.client, "host", None),
        )
        if not api_key or not api_key.user_id:
            return None

        user = await self.auth_provider.get_user(api_key.user_id)
        if not user:
            return None

        # Pre-fetch delegations for sync check_access
        if self.auth_provider.delegation_manager:
            request.state.delegations = (
                await self.auth_provider.delegation_manager.get_active_delegations(
                    user.user_id,
                )
            )

        return user


__all__ = [
    "ApiKeyAuthenticator",
]
