"""User and token storage interfaces and implementations"""

from __future__ import annotations

import secrets
from typing import Any, Protocol, runtime_checkable

from quadkit.auth.models.user import User, UserCredentials


@runtime_checkable
class CachedUserStore(Protocol):
    """Protocol for read-through cache user stores (point-lookup only).

    Implementations such as :class:`RedisUserStore` are highly efficient for
    ``get_user_by_id`` but are **not** designed for full enumeration
    operations like ``list_users`` or ``count_users``.  Use a relational or
    document-oriented :class:`UserStoreProtocol` as the primary source of truth and
    pair it with a :class:`CachedUserStore` for hot-path reads.
    """

    async def get_user_by_id(self, user_id: str) -> User | None:
        """Return the user with *user_id*, or ``None`` if not found."""
        ...

    async def create_user(
        self,
        name: str,
        email: str,
        hashed_password: str | None,
        roles: list[str] | None = None,
        permissions: list[str] | None = None,
        profile: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> User:
        """Create and cache a user entry."""
        ...

    async def update_user(self, user: User) -> None:
        """Update a cached user entry."""
        ...

    async def delete_user(self, user_id: str) -> None:
        """Evict and delete a cached user entry."""
        ...


@runtime_checkable
class UserStoreProtocol(Protocol):
    """Protocol for user storage implementations."""

    async def create_user(
        self,
        name: str,
        email: str,
        hashed_password: str | None,
        roles: list[str] | None = None,
        permissions: list[str] | None = None,
        profile: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> User:
        """Create a new user.

        Accepts arbitrary keyword arguments for backwards compatibility
        (e.g. ``is_verified``) which may be ignored by some implementations.
        Stores credential data (``hashed_password``) internally and makes it
        accessible via :meth:`get_credentials`.
        """
        ...

    async def get_user_by_id(self, user_id: str) -> User | None:
        """Get user by ID"""
        ...

    async def get_user_by_email(self, email: str) -> User | None:
        """Get user by email"""
        ...

    async def update_user(self, user: User) -> None:
        """Update non-credential user information.

        Does **not** update password hashes.  Use :meth:`update_credentials`
        for password changes.
        """
        ...

    async def delete_user(self, user_id: str) -> None:
        """Delete a user"""
        ...

    async def list_users(self, skip: int = 0, limit: int = 100) -> list[User]:
        """List users with pagination"""
        ...

    async def count_users(self) -> int:
        """Count total users"""
        ...

    async def get_credentials(self, user_id: str) -> UserCredentials | None:
        """Return the :class:`UserCredentials` for *user_id*, or ``None``.

        Use this for all authentication and password-related operations
        instead of reading fields directly from :class:`User`.
        """
        ...

    async def update_credentials(self, creds: UserCredentials) -> None:
        """Persist updated credential data for the user identified by
        ``creds.user_id``.

        This is the only sanctioned way to change a stored password hash.
        """
        ...


class InMemoryUserStore(UserStoreProtocol):
    """Simple in-memory user store for development/testing"""

    def __init__(self) -> None:
        self.users: dict[str, User] = {}
        self.name_index: dict[str, str] = {}
        self.email_index: dict[str, str] = {}
        # Credentials stored separately from public User data
        self._credentials: dict[str, UserCredentials] = {}

    async def create_user(
        self,
        name: str,
        email: str,
        hashed_password: str | None,
        roles: list[str] | None = None,
        permissions: list[str] | None = None,
        profile: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> User:
        """Create a new user"""
        if name in self.name_index:
            raise ValueError(f"Name '{name}' already exists")
        if email in self.email_index:
            raise ValueError(f"Email '{email}' already exists")

        user_id = secrets.token_urlsafe(16)

        is_verified = bool(kwargs.get("is_verified", False))

        user = User(
            user_id=user_id,
            name=name,
            email=email,
            roles=list(roles or []),
            permissions=list(permissions or []),
            profile=profile or {},
            is_verified=is_verified,
        )

        self.users[user_id] = user
        self.name_index[name] = user_id
        self.email_index[email] = user_id
        # Store credentials separately
        self._credentials[user_id] = UserCredentials(
            user_id=user_id,
            hashed_password=hashed_password,
        )

        return user

    async def get_user_by_id(self, user_id: str) -> User | None:
        """Get user by ID"""
        return self.users.get(user_id)

    async def get_user_by_email(self, email: str) -> User | None:
        """Get user by email"""
        user_id = self.email_index.get(email)
        return self.users.get(user_id) if user_id else None

    async def get_user_by_username(self, username: str) -> User | None:
        """Get user by username (name)."""
        user_id = self.name_index.get(username)
        return self.users.get(user_id) if user_id else None

    async def update_user(self, user: User) -> None:
        """Update user information"""
        if user.user_id not in self.users:
            raise ValueError(f"User '{user.user_id}' not found")

        self.users[user.user_id] = user
        # Update indexes if name or email changed
        if user.name is not None:
            self.name_index[user.name] = user.user_id
        if user.email is not None:
            self.email_index[user.email] = user.user_id

    async def delete_user(self, user_id: str) -> None:
        """Delete a user"""
        user = self.users.get(user_id)
        if user:
            del self.users[user_id]
            if user.name is not None:
                del self.name_index[user.name]
            if user.email is not None:
                del self.email_index[user.email]
        self._credentials.pop(user_id, None)

    async def list_users(self, skip: int = 0, limit: int = 100) -> list[User]:
        """List users with pagination"""
        all_users = list(self.users.values())
        return all_users[skip : skip + limit]

    async def count_users(self) -> int:
        """Count total users"""
        return len(self.users)

    async def get_credentials(self, user_id: str) -> UserCredentials | None:
        """Return stored credentials for *user_id*."""
        return self._credentials.get(user_id)

    async def update_credentials(self, creds: UserCredentials) -> None:
        """Persist updated credentials for the user."""
        if creds.user_id not in self.users:
            raise ValueError(f"User '{creds.user_id}' not found")
        self._credentials[creds.user_id] = creds


__all__ = ["CachedUserStore", "InMemoryUserStore", "UserStoreProtocol"]
