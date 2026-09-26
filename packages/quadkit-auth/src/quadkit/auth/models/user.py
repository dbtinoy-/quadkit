"""User model.

Implements the AuthenticatedUserProtocol protocol without heavy dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast
import uuid

from quadkit.domain import DomainModel
from quadkit.validation import Field


@dataclass(init=False)
class UserCredentials(DomainModel):
    """Sensitive credential data for a user.

    This model holds fields that must **never** appear in API responses or
    public-facing representations.
    """

    user_id: str = Field(description="The owning user's identifier")
    hashed_password: str | None = Field(default=None, description="Hashed password")
    previous_hashes: list[str] = Field(
        default_factory=list, description="Password history for reuse prevention"
    )


@dataclass(init=False)
class User(DomainModel):
    """User model representing an authenticated user.

    This model serves as the core user representation within the auth package.
    It implements the AuthenticatedUserProtocol protocol.
    """

    user_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Primary user identifier",
    )
    email: str = Field(default="", description="User email address")
    name: str | None = Field(default=None, description="Display name")
    is_active: bool = Field(default=True, description="Account active status")
    is_verified: bool = Field(default=False, description="Email verification status")
    is_superuser: bool = Field(default=False, description="Administrative status")

    roles: list[str] = Field(default_factory=list, description="Assigned roles")
    permissions: list[str] = Field(
        default_factory=list, description="Directly assigned permissions"
    )

    # Profile and metadata
    profile: dict[str, Any] = Field(
        default_factory=dict, description="User profile data"
    )

    # Timestamps and tracking
    created_at: datetime | None = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Account creation timestamp",
    )
    updated_at: datetime | None = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Last update timestamp",
    )
    last_login_at: datetime | None = Field(
        default=None, description="Last successful login timestamp"
    )
    login_count: int = Field(default=0, description="Total number of logins")

    # Optional metadata for specialized use cases
    delegations: list[Any] = Field(
        default_factory=list, description="Active identity delegations"
    )
    _request_metadata: dict[str, Any] = Field(
        default_factory=dict,
        exclude=True,
        description="Internal request metadata (excluded from dump)",
    )

    def has_role(self, role: str) -> bool:
        """Check if user has a specific role."""
        return role in self.roles

    def has_permission(self, permission: str) -> bool:
        """Check if user has a specific permission."""
        return permission in self.permissions

    def with_role(self, role: str) -> User:
        """Return a new User with the given role added."""
        if role in self.roles:
            return self
        return cast(
            "User",
            self.model_copy(
                update={
                    "roles": [*self.roles, role],
                    "updated_at": datetime.now(UTC),
                }
            ),
        )

    def without_role(self, role: str) -> User:
        """Return a new User with the given role removed."""
        if role not in self.roles:
            return self
        return cast(
            "User",
            self.model_copy(
                update={
                    "roles": [r for r in self.roles if r != role],
                    "updated_at": datetime.now(UTC),
                }
            ),
        )

    def with_permission(self, permission: str) -> User:
        """Return a new User with the given permission added."""
        if permission in self.permissions:
            return self
        return cast(
            "User",
            self.model_copy(
                update={
                    "permissions": [*self.permissions, permission],
                    "updated_at": datetime.now(UTC),
                }
            ),
        )

    def without_permission(self, permission: str) -> User:
        """Return a new User with the given permission removed."""
        if permission not in self.permissions:
            return self
        return cast(
            "User",
            self.model_copy(
                update={
                    "permissions": [p for p in self.permissions if p != permission],
                    "updated_at": datetime.now(UTC),
                }
            ),
        )

    def record_login(self) -> User:
        """Return a new User with the current login recorded."""
        return cast(
            "User",
            self.model_copy(
                update={
                    "last_login_at": datetime.now(UTC),
                    "login_count": self.login_count + 1,
                    "updated_at": datetime.now(UTC),
                }
            ),
        )

    def to_public_dict(self) -> dict[str, Any]:
        """Return a safe public representation of the user."""
        return self.model_dump(exclude={"_request_metadata"})

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> User:
        """Create from dictionary."""
        # Handle user_id/id alias if needed (DomainModel often handles aliases if configured)
        if "user_id" not in data and "id" in data:
            data["user_id"] = data["id"]
        return cast("User", cls.model_validate(data))


__all__ = [
    "User",
    "UserCredentials",
]
