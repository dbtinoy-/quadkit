"""MFA model for Quadkit Auth."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class UserMFA:
    """Represents MFA configuration for a user."""

    mfa_id: str
    user_id: str
    mfa_type: str = "totp"
    secret: str = ""
    is_enabled: bool = False
    last_used_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


__all__ = [
    "UserMFA",
]
