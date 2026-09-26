from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from quadkit.domain import DomainModel
from quadkit.validation import Field


@dataclass(init=False)
class UserProfile(DomainModel):
    user_id: str
    name: str
    email: str
    created_at: datetime
    is_active: bool = True
    is_verified: bool = False
    updated_at: datetime | None = None
    last_login_at: datetime | None = None
    login_count: int = 0
    roles: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    profile: dict = Field(default_factory=dict)


__all__ = [
    "UserProfile",
]
