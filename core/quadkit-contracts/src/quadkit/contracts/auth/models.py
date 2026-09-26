"""Authentication data models and protocols.

Shared auth data models (pure dataclasses with no external deps) live here
so both quadkit-auth and other packages can reference them without
creating cross-extension imports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class UserIdentityProtocol(Protocol):
    """Protocol for a user's identity."""

    @property
    def user_id(self) -> str: ...

    @property
    def email(self) -> str: ...


@dataclass(frozen=True)
class UserSession:
    """User session data model.

    Tracks a specific device/session for a user.  Defined in contracts so
    both quadkit-auth and other packages can share the type without
    creating a cross-extension dependency.
    """

    session_id: str
    user_id: str
    device_id: str
    ip_address: str | None = None
    user_agent: str | None = None
    geo_location: dict[str, Any] = field(default_factory=dict)
    fingerprint: dict[str, Any] = field(default_factory=dict)
    is_active: bool = True
    expires_at: datetime | None = None
    last_active_at: datetime | None = None
    mfa_verified_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def is_expired(self) -> bool:
        """Return True if the session has passed its expiry timestamp."""
        if not self.expires_at:
            return False
        now = datetime.now(UTC) if self.expires_at.tzinfo else datetime.now()
        return self.expires_at < now


@dataclass(frozen=True)
class VerifiedIdentityClaims:
    """Verified external identity claims returned by OAuth providers.

    This value object captures the normalized claims extracted after a
    provider-specific verification step. It is intentionally provider-neutral
    so apps can hand the result to an identity resolver without touching raw
    HTTP responses or provider-specific dict shapes.
    """

    provider: str
    provider_user_id: str
    email: str | None = None
    email_verified: bool = False
    name: str | None = None
    picture: str | None = None
    issuer: str | None = None
    audience: str | None = None
    expires_at: datetime | None = None
    issued_at: datetime | None = None
    raw_data: dict[str, Any] = field(default_factory=dict)


__all__ = ["UserIdentityProtocol", "UserSession", "VerifiedIdentityClaims"]
