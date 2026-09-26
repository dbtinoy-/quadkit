"""Type definitions for Quadkit Auth."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from quadkit.auth.models import AuthToken
from quadkit.auth.models.user import User
from quadkit.contracts.auth.roles import RoleDefinition
from quadkit.domain import DomainModel
from quadkit.validation import Field

if TYPE_CHECKING:
    from quadkit.contracts.core import HealthStatus


class AuthStatus(StrEnum):
    """Authentication status values."""

    AUTHENTICATED = "authenticated"
    UNAUTHENTICATED = "unauthenticated"
    TOKEN_EXPIRED = "token_expired"  # noqa: S105  # status name, not a credential
    TOKEN_INVALID = "token_invalid"  # noqa: S105  # status name, not a credential
    USER_INACTIVE = "user_inactive"
    USER_NOT_VERIFIED = "user_not_verified"


class TokenType(StrEnum):
    """Token type values."""

    BEARER = "Bearer"
    BASIC = "Basic"
    API_KEY = "ApiKey"


class UserStatus(StrEnum):
    """User account status values."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING_VERIFICATION = "pending_verification"
    DELETED = "deleted"


@dataclass(init=False)
class GuardContext(DomainModel):
    """Context passed to authorization guards."""

    user: User | None = Field(default=None, description="Authenticated user")
    request: Any | None = Field(default=None, description="Raw request object")
    request_context_user_id: str | None = Field(
        default=None,
        description="Authenticated user ID from the normalized request context",
    )
    route: str | None = Field(default=None, description="Target route name")
    method: str | None = Field(default=None, description="HTTP method")
    path: str | None = Field(default=None, description="Request path")
    headers: dict[str, str] = Field(default_factory=dict, description="Request headers")
    params: dict[str, Any] = Field(default_factory=dict, description="Route parameters")


@dataclass(init=False)
class AuthResult(DomainModel):
    """Result of an authentication attempt."""

    success: bool = Field(description="Whether authentication succeeded")
    status: AuthStatus = Field(description="Status code of the attempt")
    user: User | None = Field(default=None, description="Authenticated user instance")
    token: AuthToken | None = Field(default=None, description="Generated auth token")
    message: str | None = Field(
        default=None, description="Optional error/status message"
    )


@dataclass(init=False)
class OAuth2UserInfo(DomainModel):
    """User information returned by an OAuth2 provider."""

    provider: str = Field(description="OAuth2 provider name")
    provider_user_id: str = Field(description="Provider-specific user ID")
    email: str | None = Field(default=None, description="User email")
    email_verified: bool = Field(
        default=False,
        description="Whether the IdP verified the email address",
    )
    username: str | None = Field(default=None, description="Provider username")
    name: str | None = Field(default=None, description="Display name")
    avatar_url: str | None = Field(default=None, description="Profile image URL")
    raw_data: dict[str, Any] | None = Field(
        default=None, description="Original provider response"
    )

    def __post_init__(self) -> None:
        """Populate ``name`` from ``username`` when ``name`` is not supplied."""
        if self.username and not self.name:
            self.name = self.username


@dataclass(init=False)
class AuthHealthResult(DomainModel):
    """Health check result for auth components."""

    status: HealthStatus = Field(description="Overall component health status")
    message: str = Field(description="Health status message")
    users_count: int = Field(default=0, description="Number of users in store")
    components: dict[str, dict[str, Any]] = Field(
        default_factory=dict, description="Sub-component health details"
    )


@dataclass(frozen=True)
class TokenPair:
    """A minimal access + refresh token pair.

    Returned by rotation operations (e.g.
    :meth:`~quadkit.auth.authn.jwt.JWTTokenManager.refresh_with_rotation`)
    as a lightweight, immutable carrier for the two new token strings.

    Attributes:
        access: The newly issued access token JWT string.
        refresh: The newly issued refresh token JWT string.
    """

    access: str
    refresh: str


__all__ = [
    "AuthHealthResult",
    "AuthResult",
    "AuthStatus",
    "AuthToken",
    "GuardContext",
    "OAuth2UserInfo",
    "RoleDefinition",
    "TokenPair",
    "TokenType",
    "User",
    "UserStatus",
]
