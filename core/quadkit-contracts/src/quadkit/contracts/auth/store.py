"""User store protocols.

Segregated interfaces for user data access following ISP.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from quadkit.contracts.auth.user import UserProtocol


@runtime_checkable
class UserReaderProtocol(Protocol):
    """Protocol for reading user data.

    Use for query-only operations (CQRS query side).
    """

    async def get_by_id(self, user_id: str) -> UserProtocol | None:
        """Get user by ID.

        Args:
            user_id: User identifier.

        Returns:
            User if found, None otherwise.
        """
        ...

    async def get_by_email(self, email: str) -> UserProtocol | None:
        """Get user by email.

        Args:
            email: User email address.

        Returns:
            User if found, None otherwise.
        """
        ...

    async def get_by_username(self, username: str) -> UserProtocol | None:
        """Get user by username.

        Args:
            username: Username to look up.

        Returns:
            User if found, None otherwise.
        """
        ...

    async def list_users(
        self,
        skip: int = 0,
        limit: int = 100,
    ) -> list[UserProtocol]:
        """List users with pagination.

        Args:
            skip: Number of records to skip.
            limit: Maximum records to return.

        Returns:
            List of users.
        """
        ...

    async def count_users(self) -> int:
        """Count total users.

        Returns:
            Total user count.
        """
        ...


@runtime_checkable
class UserWriterProtocol(Protocol):
    """Protocol for writing user data.

    Use for command-only operations (CQRS command side).
    """

    async def create(self, user: UserProtocol) -> UserProtocol:
        """Create a new user.

        Args:
            user: User to create.

        Returns:
            Created user.
        """
        ...

    async def update(self, user: UserProtocol) -> UserProtocol:
        """Update an existing user.

        Args:
            user: User to update.

        Returns:
            Updated user.
        """
        ...

    async def delete(self, user_id: str) -> bool:
        """Delete a user.

        Args:
            user_id: User identifier.

        Returns:
            True if deleted, False if not found.
        """
        ...


@runtime_checkable
class UserStoreProtocol(UserReaderProtocol, UserWriterProtocol, Protocol):
    """Combined user store protocol for read/write operations.

    This protocol combines UserReaderProtocol and UserWriterProtocol for convenience
    in implementations that provide both read and write capabilities.
    """


__all__ = [
    "UserReaderProtocol",
    "UserStoreProtocol",
    "UserWriterProtocol",
]
