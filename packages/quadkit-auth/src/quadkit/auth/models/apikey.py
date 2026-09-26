"""API Key data model.

Used for service-to-service authentication.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(frozen=True)
class APIKey:
    """API Key data model.

    Used for service-to-service authentication.
    """

    key_id: str
    name: str
    key_hash: str
    prefix: str
    user_id: str
    scopes: list[str] = field(default_factory=list)
    expires_at: datetime | None = None
    last_used_at: datetime | None = None
    last_used_ip: str | None = None
    revoked_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def is_active(self) -> bool:
        """Check if the key is active and not expired or revoked."""
        if self.revoked_at is not None:
            return False
        if self.expires_at is None:
            return True
        # Stored timestamps may be aware (Postgres TIMESTAMPTZ, ISO-8601
        # text normalised by the SQL repositories) or naive (in-memory
        # stores).  Naive values are assumed to be UTC — the convention
        # used everywhere else in this package.
        expires_at = (
            self.expires_at
            if self.expires_at.tzinfo is not None
            else self.expires_at.replace(tzinfo=UTC)
        )
        return expires_at > datetime.now(UTC)


__all__ = [
    "APIKey",
]
