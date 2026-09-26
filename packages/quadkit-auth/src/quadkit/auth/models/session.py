"""Session model for Quadkit Auth."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from typing import Any


@dataclass(frozen=True)
class UserSession:
    """User session data model.

    Tracks a specific device/session for a user.
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
    token_jti: str | None = None  # JTI (JWT ID) of the associated access token

    def is_expired(self) -> bool:
        """Return ``True`` if this session has passed its expiry time."""
        if not self.expires_at:
            return False

        # Ensure we compare aware datetimes
        now = datetime.now(UTC) if self.expires_at.tzinfo else datetime.now()
        return self.expires_at < now

    def is_valid(self) -> bool:
        """Return ``True`` if the session is active and has not expired.

        A session is considered valid when :attr:`is_active` is ``True``
        *and* :meth:`is_expired` returns ``False``.
        """
        return self.is_active and not self.is_expired()

    def remaining_ttl(self) -> timedelta | None:
        """Return the time remaining until this session expires.

        Returns:
            A :class:`~datetime.timedelta` representing time until expiry,
            or ``None`` when no expiry is configured.  Returns
            ``timedelta(0)`` (zero duration) when the session has already
            expired.
        """
        if self.expires_at is None:
            return None

        now = datetime.now(UTC) if self.expires_at.tzinfo else datetime.now()
        delta = self.expires_at - now
        return delta if delta.total_seconds() > 0 else timedelta(0)

    def refresh(
        self,
        expires_at: datetime,
        last_active_at: datetime | None = None,
    ) -> UserSession:
        """Return a new :class:`UserSession` with an updated expiry time.

        Because :class:`UserSession` is a frozen dataclass, this method
        returns a **new** instance rather than mutating the current one.

        Args:
            expires_at: The new expiry timestamp for the refreshed session.
            last_active_at: Optional new last-active timestamp.  Defaults
                to ``datetime.now(UTC)`` when the session uses aware
                datetimes, else ``datetime.now()``.

        Returns:
            A copy of this session with :attr:`expires_at` (and
            :attr:`last_active_at`) updated.
        """
        if last_active_at is None:
            last_active_at = datetime.now(UTC) if expires_at.tzinfo else datetime.now()
        return replace(self, expires_at=expires_at, last_active_at=last_active_at)


__all__ = [
    "UserSession",
]
