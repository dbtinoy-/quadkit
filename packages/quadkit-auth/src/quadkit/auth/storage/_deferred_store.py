"""Deferred-resolution user store.

The SQL identity store needs the application's
``DatabaseProviderProtocol``, which lives in whatever module the
application composed for persistence. QuadKit's module-visibility rules
mean a provider booting inside the (global) auth module cannot always
*see* that binding during ``boot()`` — non-global modules' exports are
only visible to modules that import them. The framework's answer to
this shape is deferred resolution (the same idiom as the notification
inbox store factory and this package's blacklist resolver): hold a
factory over the root resolver and materialise the real store on first
use, when resolution runs in the caller's context with no module
restriction.

This wrapper gives the authentication provider one stable
:class:`UserStoreProtocol` object to hand to its services at
construction time. The factory runs at most once; concurrent first
calls serialise on a lock. A factory failure (e.g. no database
provider registered at all) propagates to the caller — deferred never
means silently degraded.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from quadkit.auth.models.user import User, UserCredentials
    from quadkit.auth.storage.token_store import UserStoreProtocol

__all__ = ["DeferredUserStore"]


class DeferredUserStore:
    """User store that materialises its delegate on first use.

    Args:
        factory: Async callable producing the real store. Invoked at
            most once, lazily, on the first protocol call.
    """

    def __init__(
        self,
        factory: Callable[[], Awaitable[UserStoreProtocol]],
    ) -> None:
        self._factory = factory
        self._delegate: UserStoreProtocol | None = None
        self._lock = asyncio.Lock()

    @property
    def resolved_store(self) -> UserStoreProtocol | None:
        """The materialised delegate, or ``None`` before first use."""
        return self._delegate

    async def resolve(self) -> UserStoreProtocol:
        """Materialise (once) and return the delegate store."""
        if self._delegate is not None:
            return self._delegate
        async with self._lock:
            if self._delegate is None:
                self._delegate = await self._factory()
            return self._delegate

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
        """Create a user in the delegate store."""
        store = await self.resolve()
        return await store.create_user(
            name,
            email,
            hashed_password,
            roles=roles,
            permissions=permissions,
            profile=profile,
            **kwargs,
        )

    async def get_user_by_id(self, user_id: str) -> User | None:
        """Return the user with *user_id*, or ``None``."""
        store = await self.resolve()
        return await store.get_user_by_id(user_id)

    async def get_user_by_email(self, email: str) -> User | None:
        """Return the user with *email*, or ``None``."""
        store = await self.resolve()
        return await store.get_user_by_email(email)

    async def update_user(self, user: User) -> None:
        """Update non-credential user information in the delegate."""
        store = await self.resolve()
        await store.update_user(user)

    async def delete_user(self, user_id: str) -> None:
        """Delete a user from the delegate store."""
        store = await self.resolve()
        await store.delete_user(user_id)

    async def list_users(self, skip: int = 0, limit: int = 100) -> list[User]:
        """List users from the delegate store with pagination."""
        store = await self.resolve()
        return await store.list_users(skip=skip, limit=limit)

    async def count_users(self) -> int:
        """Count users in the delegate store."""
        store = await self.resolve()
        return await store.count_users()

    async def get_credentials(self, user_id: str) -> UserCredentials | None:
        """Return stored credentials from the delegate store."""
        store = await self.resolve()
        return await store.get_credentials(user_id)

    async def update_credentials(self, creds: UserCredentials) -> None:
        """Persist updated credentials via the delegate store."""
        store = await self.resolve()
        await store.update_credentials(creds)
