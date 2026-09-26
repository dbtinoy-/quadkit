"""Authentication token models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from quadkit.auth import constants as const
from quadkit.domain import DomainModel
from quadkit.validation import Field

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(init=False)
class AuthToken(DomainModel):
    """Authentication token response."""

    token: str = Field(description="The primary authentication token string")
    expires_at: datetime = Field(description="Token expiration timestamp")
    refresh_token: str | None = Field(
        default=None, description="Optional refresh token"
    )
    refresh_expires_at: datetime | None = Field(
        default=None, description="Refresh token expiration timestamp"
    )
    token_type: str = Field(
        default=const.DEFAULT_TOKEN_TYPE, description="Token type (e.g. Bearer)"
    )


__all__ = [
    "AuthToken",
]
