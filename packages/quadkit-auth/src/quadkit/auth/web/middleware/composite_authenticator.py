"""Composite request authenticator — the concrete ``AuthenticatorProtocol``.

``AuthModule.configure()`` declares ``exports=[AuthenticatorProtocol, ...]``,
but no single class previously satisfied and was bound to that key: each of
:class:`~quadkit.auth.web.middleware.api_key_authenticator.ApiKeyAuthenticator`,
:class:`~quadkit.auth.web.middleware.session_authenticator.SessionAuthenticator`,
and :class:`~quadkit.auth.web.middleware.jwt_authenticator.JwtAuthenticator`
only authenticate *one* credential scheme each, and were previously wired
solely as private attributes of
:class:`~quadkit.auth.web.middleware.auth.AuthMiddleware` — never as a
standalone, container-resolvable service.

This module provides that missing piece: a small composite that tries each
scheme in the same order :class:`AuthMiddleware` does (API key, then
session, then JWT) and returns the first authenticated user, or ``None`` if
none match. It structurally satisfies ``AuthenticatorProtocol``
(``async def authenticate(self, request) -> Any | None``) so it can be
bound to that protocol and resolved by any code that only depends on the
protocol rather than on ``AuthMiddleware`` itself.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.auth.web.middleware.api_key_authenticator import ApiKeyAuthenticator
from quadkit.auth.web.middleware.jwt_authenticator import JwtAuthenticator
from quadkit.auth.web.middleware.session_authenticator import SessionAuthenticator
from quadkit.auth.web.middleware.token_extractor import TokenExtractor

if TYPE_CHECKING:
    from quadkit.contracts.auth import AuthProviderProtocol

__all__ = ["CompositeRequestAuthenticator"]


class CompositeRequestAuthenticator:
    """Authenticate a request by trying API key, session, then JWT.

    Mirrors :meth:`AuthMiddleware.authenticate_request`'s dispatch order
    without that class's ASGI-specific concerns (token caching, lockout
    tracking, scope mutation) — those remain the middleware's job. This
    class exists purely to give ``AuthenticatorProtocol`` a real,
    container-resolvable implementation.

    Args:
        auth_provider: The bound ``AuthProviderProtocol`` implementation
            (normally :class:`~quadkit.auth.di.sub_providers.authentication_provider.AuthenticationProvider`).
    """

    def __init__(self, auth_provider: AuthProviderProtocol) -> None:
        self._auth_provider = auth_provider
        self._token_extractor = TokenExtractor(
            type("Config", (), {"header_name": "Authorization", "scheme": "Bearer"})()
        )
        self._api_key_authenticator = ApiKeyAuthenticator(auth_provider)
        self._session_authenticator = SessionAuthenticator(auth_provider)
        self._jwt_authenticator = JwtAuthenticator(auth_provider)

    async def authenticate(self, request: Any) -> Any | None:
        """Authenticate *request* via API key, session, then JWT, in order.

        Args:
            request: The incoming HTTP request.

        Returns:
            The authenticated user, or ``None`` if no scheme matched.
        """
        token = self._token_extractor.extract_token(request)
        if token:
            user = await self._api_key_authenticator.authenticate(token, request)
            if user is not None:
                return user

        user = await self._session_authenticator.authenticate(request)
        if user is not None:
            return user

        return await self._jwt_authenticator.authenticate(request)
