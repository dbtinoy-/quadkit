"""User protocols.

Protocols defining user identity contracts.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class UserProtocol(Protocol):
    """Protocol for user entity.

    Defines the minimal contract for a user in the system.
    """

    @property
    def user_id(self) -> str:
        """Unique user identifier."""
        ...

    @property
    def email(self) -> str:
        """User email address."""
        ...

    @property
    def is_active(self) -> bool:
        """Whether user account is active."""
        ...


@runtime_checkable
class AuthenticatedUserProtocol(Protocol):
    """Protocol for authenticated user attached to requests.

    This protocol defines the contract that any authenticated user
    implementation must follow for type-safe user handling.

    Example:
        ```python
        def get_user_profile(user: AuthenticatedUserProtocol) -> dict:
            return {"user_id": user.user_id, "roles": user.roles}
        ```
    """

    @property
    def user_id(self) -> str:
        """Unique identifier for the user."""
        ...

    @property
    def name(self) -> str:
        """Name of the authenticated user."""
        ...

    @property
    def email(self) -> str:
        """Email address of the user."""
        ...

    @property
    def is_active(self) -> bool:
        """Whether the user account is active."""
        ...

    @property
    def is_verified(self) -> bool:
        """Whether the user's email is verified."""
        ...

    @property
    def roles(self) -> list[str]:
        """List of roles assigned to the user."""
        ...

    @property
    def permissions(self) -> list[str]:
        """List of permissions granted to the user."""
        ...

    def has_role(self, role: str) -> bool:
        """Check if user has a specific role.

        Args:
            role: The role to check for.

        Returns:
            True if the user has the role.
        """
        ...

    def has_permission(self, permission: str) -> bool:
        """Check if user has a specific permission.

        Args:
            permission: The permission to check for.

        Returns:
            True if the user has the permission.
        """
        ...


__all__ = [
    "AuthenticatedUserProtocol",
    "UserProtocol",
]
