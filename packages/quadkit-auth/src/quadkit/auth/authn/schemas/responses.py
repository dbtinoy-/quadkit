from __future__ import annotations

from dataclasses import dataclass

from quadkit.domain import DomainModel
from quadkit.validation import Field


@dataclass(init=False)
class TokenResponse(DomainModel):
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field("bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration time in seconds")
    refresh_token: str | None = Field(None, description="Refresh token")
    user: dict = Field(..., description="User information")


__all__ = [
    "TokenResponse",
]
