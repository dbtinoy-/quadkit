"""Root hook payload surface for quadkit-auth.

Defines canonical payload dataclasses for auth-lifecycle hook points. Actual
hook registration and invocation use the framework's string-keyed
``HookRegistryProtocol`` action/filter APIs.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "AuthAuthenticationFailedHook",
    "AuthTokenIssuedHook",
    "AuthTokenRefreshedHook",
    "AuthTokenRevokedHook",
    "AuthUserAuthenticatedHook",
]


@dataclass(frozen=True, kw_only=True)
class AuthUserAuthenticatedHook:
    """Payload fired when a user successfully authenticates.

    Attributes:
        user_id: Identifier of the authenticated user.
        method: Authentication method used (e.g. ``"password"``, ``"oauth2"``).
    """

    user_id: str
    method: str


@dataclass(frozen=True, kw_only=True)
class AuthAuthenticationFailedHook:
    """Payload fired when an authentication attempt fails.

    Attributes:
        method: Authentication method that was attempted.
        reason: Short description of why authentication failed.
    """

    method: str
    reason: str


@dataclass(frozen=True, kw_only=True)
class AuthTokenIssuedHook:
    """Payload fired when an access or refresh token is issued.

    Attributes:
        user_id: Identifier of the user the token was issued for.
        token_type: Token kind (e.g. ``"access"``, ``"refresh"``).
    """

    user_id: str
    token_type: str


@dataclass(frozen=True, kw_only=True)
class AuthTokenRevokedHook:
    """Payload fired when a token is explicitly revoked.

    Attributes:
        user_id: Identifier of the user whose token was revoked.
        token_type: Token kind that was revoked.
    """

    user_id: str
    token_type: str


@dataclass(frozen=True, kw_only=True)
class AuthTokenRefreshedHook:
    """Payload fired when an access token is refreshed.

    Attributes:
        user_id: Identifier of the user whose token was refreshed.
        token_type: Token kind that was refreshed.
    """

    user_id: str
    token_type: str
