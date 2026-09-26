"""OAuth2 authentication flows.

This module provides OAuth2 authentication support for Quadkit, enabling
social login and OAuth2-based authentication with providers like Google,
GitHub, Facebook, and other OAuth2-compatible identity providers.

Example:
    Setting up OAuth2 authentication::

        from quadkit.auth.authn.oauth2 import OAuth2Authenticator

        authenticator = OAuth2Authenticator(
            provider="google",
            client_id="your-client-id",
            client_secret="your-client-secret",
            redirect_uri="https://yourapp.com/auth/callback"
        )

        # Get authorization URL
        auth_url = await authenticator.get_authorization_url()

        # Exchange code for tokens
        user_info = await authenticator.get_user_info(code)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from quadkit.auth.authn.oauth2_session import (
    QuadkitConnectResponse as QuadkitConnectResponse,
)
from quadkit.auth.authn.oauth2_session import (
    QuadkitConnectSession as QuadkitConnectSession,
)
from quadkit.auth.exceptions import OAuth2Error
from quadkit.auth.types import OAuth2UserInfo
from quadkit.logging import get_logger

# Initialize logger early so runtime checks can log errors
logger = get_logger(__name__)

try:
    from authlib.integrations.base_client import (
        OAuthError,
    )
    from authlib.integrations.httpx_client import (
        AsyncOAuth2Client,
    )

    HAS_AUTHLIB = True
except ImportError:
    # Provide placeholders so tests can patch these symbols even when authlib
    # isn't installed in the test environment.
    HAS_AUTHLIB = False
    OAuthError = Exception
    AsyncOAuth2Client = None


if TYPE_CHECKING:
    from quadkit.auth.models.user import User
    from quadkit.contracts.web import HTTPClientProtocol


class OAuth2IdentityProvider:
    """OAuth2 identity provider configuration."""

    def __init__(
        self,
        name: str,
        client_id: str,
        client_secret: str,
        authorize_url: str,
        access_token_url: str,
        userinfo_url: str,
        scope: str = "openid email profile",
        redirect_uri: str | None = None,
        require_pkce: bool = True,
        auth_style: int = 0,
    ):
        self.name = name
        self.client_id = client_id
        self.client_secret = client_secret
        self.authorize_url = authorize_url
        self.access_token_url = access_token_url
        self.userinfo_url = userinfo_url
        self.scope = scope
        self.redirect_uri = redirect_uri
        self.require_pkce = require_pkce
        self.auth_style = auth_style


class OAuth2Manager:
    """OAuth2 authentication manager"""

    def __init__(
        self,
        providers: dict[str, OAuth2IdentityProvider],
        http_client: HTTPClientProtocol | None = None,
    ) -> None:
        # Allow construction even when authlib isn't installed so tests can
        # assert that providers are configured. Actual network operations
        # will raise if authlib is absent.
        self.providers = providers
        self._http_client = http_client
        self._available = HAS_AUTHLIB
        if not self._available:
            logger.warning(
                "authlib not installed; OAuth2Manager created in no-op mode for tests",
            )

    def __repr__(self) -> str:
        """Return developer-friendly string representation."""
        return f"OAuth2Manager(providers={list(self.providers)!r})"

    async def get_authorization_url(
        self,
        provider_name: str,
        state: str | None = None,
    ) -> tuple[str, str, str]:
        """Get OAuth2 authorization URL, PKCE code_verifier (S256), and state.

        Returns a tuple of ``(authorization_url, code_verifier, state)``.
        Callers **must** persist both ``code_verifier`` and ``state`` and
        verify ``state`` matches on the callback to prevent CSRF attacks.

        If *state* is not supplied a cryptographically random value is
        generated automatically using :func:`secrets.token_urlsafe`."""
        import base64
        import hashlib
        import secrets

        if not self._available:
            raise RuntimeError(
                "authlib is required for OAuth2 operations; OAuth2Manager is in no-op mode",
            )

        provider = self.providers.get(provider_name)
        if not provider:
            raise ValueError(f"OAuth2 provider '{provider_name}' not configured")

        # Auto-generate state when caller does not supply one
        if state is None:
            state = secrets.token_urlsafe(32)
            logger.debug(
                "OAuth2 state not provided; auto-generating secure random state",
                provider=provider_name,
            )

        # Use custom session if http_client provided, otherwise use default httpx
        session = None
        if self._http_client:
            session = QuadkitConnectSession(self._http_client)

        client = AsyncOAuth2Client(
            client_id=provider.client_id,
            client_secret=provider.client_secret,
            redirect_uri=provider.redirect_uri,
            session=session,
        )

        # Generate a verifier for every flow so callers can persist one
        # uniform flow record.  Only advertise PKCE when the provider
        # configuration explicitly enables it; some established OAuth
        # providers reject unknown authorization parameters.
        code_verifier = secrets.token_urlsafe(64)
        authorization_kwargs: dict[str, Any] = {
            "scope": provider.scope,
            "state": state,
        }
        if provider.require_pkce:
            digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
            code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
            authorization_kwargs.update(
                code_challenge=code_challenge,
                code_challenge_method="S256",
            )

        authorization_url, _ = client.create_authorization_url(
            provider.authorize_url,
            **authorization_kwargs,
        )

        return str(authorization_url), code_verifier, state

    async def exchange_code_for_token(
        self,
        provider_name: str,
        code: str,
        code_verifier: str | None = None,
    ) -> dict[str, Any]:
        """Exchange authorization code for access token, optionally with PKCE code_verifier"""
        provider = self.providers.get(provider_name)
        if not provider:
            raise ValueError(f"OAuth2 provider '{provider_name}' not configured")

        if provider.require_pkce and code_verifier is None:
            raise OAuth2Error(
                f"PKCE code_verifier is required for provider '{provider_name}'; "
                "include the code_verifier returned by get_authorization_url()"
            )

        # Use custom session if http_client provided, otherwise use default httpx
        session = None
        if self._http_client:
            session = QuadkitConnectSession(self._http_client)

        # New-api's generic provider uses form credentials for its explicit
        # params (style 1) mode and RFC 6749 HTTP Basic for style 2. Style 0
        # is the useful automatic mode: try the form variant first (the
        # new-api default), then retry with Basic when the provider rejects
        # that client-authentication method. Passing the method to Authlib is
        # important: adding client_id to kwargs alone would still leave
        # Authlib's default Basic header in place.
        auth_methods = (
            ["client_secret_post", "client_secret_basic"]
            if provider.auth_style == 0
            else [
                "client_secret_basic"
                if provider.auth_style == 2
                else "client_secret_post",
            ]
        )

        if not self._available:
            raise RuntimeError(
                "authlib is required for OAuth2 operations; OAuth2Manager is in no-op mode",
            )

        fetch_kwargs: dict[str, Any] = {"code": code}
        if code_verifier:
            fetch_kwargs["code_verifier"] = code_verifier

        for attempt, token_auth_method in enumerate(auth_methods):
            client = AsyncOAuth2Client(
                client_id=provider.client_id,
                client_secret=provider.client_secret,
                redirect_uri=provider.redirect_uri,
                token_endpoint_auth_method=token_auth_method,
                session=session,
            )
            try:
                return cast(
                    "dict[str, Any]",
                    await client.fetch_token(provider.access_token_url, **fetch_kwargs),
                )
            except OAuthError as e:
                # Only retry errors that identify client authentication as the
                # problem. Retrying invalid_grant would submit a one-time code
                # twice and hide the real callback failure.
                if (
                    provider.auth_style == 0
                    and attempt == 0
                    and self._should_retry_basic_auth(e)
                ):
                    logger.info(
                        "OAuth2 token endpoint rejected form client authentication; retrying Basic",
                        provider=provider_name,
                        error=getattr(e, "error", None),
                    )
                    continue
                logger.exception("OAuth2 token exchange failed")
                raise ValueError(f"OAuth2 token exchange failed: {e!s}") from e

        # The loop always returns or raises, but keep a defensive guard for
        # type-checkers and future auth-method additions.
        raise ValueError("OAuth2 token exchange failed: no token authentication method succeeded")

    @staticmethod
    def _should_retry_basic_auth(error: Exception) -> bool:
        """Return whether an OAuth error is specific enough for style-0 retry.

        Authlib exposes the RFC error code on ``OAuthError.error``. A few
        providers only signal the rejected method through an HTTP status, so
        accept the conventional 401/403 response as well. Do not retry generic
        OAuth failures such as ``invalid_grant``: authorization codes are
        single-use and a second request would be misleading.
        """
        error_code = str(getattr(error, "error", "") or "").lower()
        if error_code in {"invalid_client", "unauthorized_client"}:
            return True
        return getattr(error, "status_code", None) in {401, 403}

    async def get_user_info(
        self,
        provider_name: str,
        token: dict[str, Any],
    ) -> dict[str, Any]:
        """Get user information from OAuth2 provider"""
        provider = self.providers.get(provider_name)
        if not provider:
            raise ValueError(f"OAuth2 provider '{provider_name}' not configured")

        # Use custom session if http_client provided, otherwise use default httpx
        session = None
        if self._http_client:
            session = QuadkitConnectSession(self._http_client)

        client = AsyncOAuth2Client(
            client_id=provider.client_id,
            client_secret=provider.client_secret,
            token=token,
            session=session,
        )

        if not self._available:
            raise RuntimeError(
                "authlib is required for OAuth2 operations; OAuth2Manager is in no-op mode",
            )

        try:
            resp = await client.get(provider.userinfo_url)
            resp.raise_for_status()
            # Handle sync or async json() implementations (tests use mocks returning dict)
            import asyncio

            maybe_json = resp.json()
            if asyncio.iscoroutine(maybe_json):
                data = await maybe_json
            else:
                data = maybe_json
            return cast("dict[str, Any]", data)
        except Exception as e:  # noqa: BLE001 — provider/HTTP failures become ValueError
            logger.exception("Failed to get user info from OAuth2 provider")
            raise ValueError(f"Failed to get user info: {e!s}") from e
        except (KeyError, TypeError, ValueError) as e:
            logger.exception("Unexpected error during OAuth2 user info retrieval")
            raise ValueError(f"Unexpected error: {e!s}") from e


class OAuth2AuthProvider:
    """Complete OAuth2 provider with user provisioning."""

    def __init__(
        self,
        oauth2_manager: OAuth2Manager,
        user_store: Any,
        oauth_identity_store: Any | None = None,
    ) -> None:
        self.oauth2_manager = oauth2_manager
        self.user_store = user_store
        self.oauth_identity_store = oauth_identity_store

    async def authenticate_with_oauth2(
        self,
        provider_name: str,
        code: str,
        code_verifier: str | None = None,
    ) -> User:
        """Authenticate user via OAuth2 and provision if needed."""

        # Exchange code for token (support PKCE via code_verifier)
        if code_verifier is None:
            token = await self.oauth2_manager.exchange_code_for_token(
                provider_name,
                code,
            )
        else:
            token = await self.oauth2_manager.exchange_code_for_token(
                provider_name,
                code,
                code_verifier=code_verifier,
            )

        # Get user info from provider
        user_info = await self.oauth2_manager.get_user_info(provider_name, token)

        # Map to OAuth2UserInfo
        oauth_user = OAuth2UserInfo(
            provider=provider_name,
            provider_user_id=user_info["id"],
            email=user_info.get("email"),
            email_verified=bool(user_info.get("email_verified", False)),
            username=(user_info.get("login") or user_info.get("username")),
            # prefer login/username over display name so that the test above
            # that expects ``testuser`` continues to pass
            name=(
                user_info.get("login")
                or user_info.get("username")
                or user_info.get("name")
                or user_info.get("email")
            ),
            avatar_url=user_info.get("avatar_url"),
            raw_data=user_info,
        )

        # Find or create user
        return await self._find_or_create_oauth_user(oauth_user)

    async def _find_or_create_oauth_user(self, oauth_user: OAuth2UserInfo) -> User:
        """Find existing user or provision new one."""

        # Try to find by email (only when the IdP verified the address)
        if oauth_user.email:
            if oauth_user.email_verified:
                existing_user = await self.user_store.get_user_by_email(
                    oauth_user.email
                )
                if existing_user:
                    from typing import cast

                    return cast("User", existing_user)
            identity_user = await self._find_by_oauth_identity(
                oauth_user.provider,
                oauth_user.provider_user_id,
            )
            if identity_user:
                return identity_user

        # Provision new user
        # ``name`` used for login; for profile we keep the display name
        # provided by the OAuth provider if available.
        display_name = None
        if oauth_user.raw_data:
            display_name = oauth_user.raw_data.get("name")
        if not display_name:
            display_name = oauth_user.name

        user = await self.user_store.create_user(
            name=oauth_user.name or oauth_user.email,
            email=oauth_user.email,
            hashed_password=None,  # No password for OAuth users
            roles=["user"],
            is_verified=oauth_user.email_verified,
            profile={
                "name": display_name,
                "avatar_url": oauth_user.avatar_url,
                "oauth_provider": oauth_user.provider,
            },
        )

        # Link OAuth identity (if store available)
        if self.oauth_identity_store:
            await self._link_oauth_identity(
                user.user_id,
                oauth_user.provider,
                oauth_user.provider_user_id,
            )

        logger.info(
            "Provisioned new user %s via %s",
            user.name,
            oauth_user.provider,
        )

        from typing import cast

        return cast("User", user)

    async def _find_by_oauth_identity(
        self,
        provider: str,
        provider_user_id: str,
    ) -> User | None:
        """Find user by OAuth identity."""
        if not self.oauth_identity_store:
            return None

        identity = await self.oauth_identity_store.get_oauth_identity(
            provider,
            provider_user_id,
        )
        if identity:
            from typing import cast

            return cast("User", await self.user_store.get_user_by_id(identity.user_id))
        return None

    async def _link_oauth_identity(
        self,
        user_id: str,
        provider: str,
        provider_user_id: str,
    ) -> None:
        """Link OAuth identity to user."""
        if not self.oauth_identity_store:
            return

        await self.oauth_identity_store.create_oauth_identity(
            user_id=user_id,
            provider=provider,
            provider_user_id=provider_user_id,
        )


__all__ = [
    "OAuth2AuthProvider",
    "OAuth2Manager",
    "QuadkitConnectResponse",
    "QuadkitConnectSession",
]
