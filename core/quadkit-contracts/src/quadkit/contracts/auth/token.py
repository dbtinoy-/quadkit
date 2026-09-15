"""Token management protocols.

Protocols for JWT token creation, validation, and refresh.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from datetime import datetime

    from quadkit.contracts.auth.exceptions import TokenError
    from quadkit.contracts.auth.user import AuthenticatedUserProtocol
    from quadkit.contracts.core.result import Result


@dataclass(frozen=True)
class VerifiedToken:
    """Decoded and validated JWT token payload.

    Returned when token verification succeeds.  All fields are extracted from
    the verified JWT claims so callers never need to inspect raw ``dict``
    payloads.

    Attributes:
        user_id: Subject claim (``sub``), identifying the token owner.
        email: Email address of the token owner.
        name: Display name of the token owner.
        roles: List of role identifiers granted to the user.
        permissions: List of permission identifiers granted to the user.
        expires_at: Absolute UTC datetime at which the token expires.
        key_id: Key ID (``kid`` header) used to sign this token.
        token_type: Token kind — ``"access"`` or ``"refresh"``.
        audience: Audience claim (``aud``), or ``None`` if absent.
    """

    user_id: str
    email: str
    name: str
    roles: list[str]
    permissions: list[str]
    expires_at: datetime
    key_id: str
    token_type: str  # "access" or "refresh"
    audience: str | None = None
    extra_claims: dict[str, Any] = field(default_factory=dict)
    """Application-defined claims not covered by the typed fields above.

    Standard registered claims (``iat``, ``exp``, ``iss``, ``nbf``, ``jti``,
    ``aud``, ``sub``) are excluded. Populated by token verification so
    callers never need to decode the raw JWT a second time.
    """


@runtime_checkable
class TokenManagerProtocol(Protocol):
    """Protocol for token management implementations.

    Defines the contract for JWT token creation, verification,
    and refresh operations.

    Example:
        ```python
        class JWTTokenManager:
            def create_token(self, user: AuthenticatedUserProtocol) -> AuthToken:
                payload = {"sub": user.user_id, "roles": user.roles}
                access = jwt.encode(payload, self._secret, algorithm="HS256")
                return AuthToken(access_token=access, ...)
        ```
    """

    def create_token(self, user: AuthenticatedUserProtocol) -> Any:
        """Create an authentication token for a user.

        Args:
            user: The authenticated user.

        Returns:
            AuthToken containing access and refresh tokens.
        """
        ...

    def verify_token(self, token: str) -> Result[VerifiedToken, TokenError]:
        """Verify and decode a token.

        Returns a ``Result`` rather than raising domain exceptions so that
        the caller can pattern-match on success vs. failure explicitly.
        Infrastructure errors (cache unavailable, network failure) are still
        raised as exceptions and must not be wrapped in ``Result``.

        Args:
            token: The JWT token string.

        Returns:
            ``Ok(VerifiedToken)`` if the token is valid and not revoked,
            or ``Err(TokenError)`` for any expected domain failure.
        """
        ...

    def refresh_token(self, refresh_token: str) -> Result[Any, TokenError]:
        """Refresh an access token using a refresh token.

        Args:
            refresh_token: The refresh token string.

        Returns:
            ``Ok(AuthToken)`` if the refresh token is valid, or
            ``Err(TokenError)`` for expected domain failures.
        """
        ...


__all__ = [
    "TokenManagerProtocol",
    "VerifiedToken",
]
