"""Database-backed user store implementations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.auth.models.user import User, UserCredentials
from quadkit.auth.storage._mongo_store import MongoDBUserStore
from quadkit.auth.storage._sql_store import SQLUserStore
from quadkit.di.decorators import inject
from quadkit.logging import get_logger
from quadkit.serialization import dumps_str, loads

if TYPE_CHECKING:
    from quadkit.contracts import DatabaseProviderProtocol

logger = get_logger(__name__)


@inject
class RedisUserStore:
    """Redis-backed user cache (read-through cache, not primary storage).

    Implements :class:`~quadkit.auth.storage.token_store.CachedUserStore` —
    it is designed for **point-lookup** operations only.  Full-scan operations
    (``list_users``, ``count_users``, ``get_user_by_email``) are intentionally
    not supported; a relational or document-oriented
    :class:`~quadkit.auth.storage.token_store.UserStoreProtocol` must be used as the
    primary source of truth.

    Stores user records as Redis hashes under ``{prefix}{user_id}``.
    Credential fields (``hashed_password``, ``previous_passwords``) are kept
    in the same Redis hash but are only accessible via :meth:`get_credentials`
    and mutated via :meth:`update_credentials`.

    Args:
        db_provider: Database provider whose ``redis`` attribute exposes
            a Redis-compatible async client.
        prefix: Key prefix applied to every user key.  Defaults to
            ``"user:"``.
        ttl: Optional time-to-live in seconds applied to every cached
            user entry.  ``None`` means entries never expire (default).

    .. warning::
        Do **not** use :class:`RedisUserStore` for operations that require
        full enumeration (``list_users``, ``count_users``,
        ``get_user_by_email``).  These methods raise :exc:`NotImplementedError`
        by design.  Use a SQL or MongoDB store for those operations.
    """

    def __init__(
        self,
        db_provider: DatabaseProviderProtocol,
        prefix: str = "user:",
        ttl: int | None = None,
    ) -> None:
        self.db_provider = db_provider
        self.prefix = prefix
        self.ttl = ttl

    async def _user_key(self, user_id: str) -> str:
        """Generate Redis key for user"""
        return f"{self.prefix}{user_id}"

    async def _user_from_data(self, data: dict[str, Any]) -> User:
        """Convert Redis hash data to a User object (credentials excluded)."""
        from datetime import datetime

        def parse_dt(val: Any) -> datetime | None:
            if not val:
                return None
            if isinstance(val, datetime):
                return val
            try:
                if isinstance(val, (int, float)):
                    return datetime.fromtimestamp(val)
                return datetime.fromisoformat(str(val))
            except (ValueError, TypeError):
                return None

        return User(
            user_id=data["id"],
            name=data["name"] if "name" in data else data.get("username"),
            email=data["email"],
            is_active=data.get("is_active", True),
            is_verified=data.get("is_verified", False),
            roles=loads(data.get("roles", "[]")),
            permissions=loads(data.get("permissions", "[]")),
            profile=loads(data.get("profile", "{}")),
            created_at=parse_dt(data.get("created_at")),
            updated_at=parse_dt(data.get("updated_at")),
            last_login_at=parse_dt(data.get("last_login_at")),
            login_count=int(data.get("login_count", 0)),
        )

    async def _data_from_user(self, user: User) -> dict[str, str]:
        """Convert User object to Redis hash fields (non-credential fields only)."""
        # BUG #40: ``dumps`` returns bytes (orjson backend); ``str(bytes)``
        # produced ``"b'[...]'`` which ``loads`` could not parse, breaking
        # every cached read after a write. Use the str-returning variant.
        data: dict[str, str] = {
            "id": user.user_id,
            "name": user.name or "",
            "email": user.email,
            "is_active": str(user.is_active),
            "is_verified": str(user.is_verified),
            "roles": dumps_str(user.roles),
            "permissions": dumps_str(user.permissions),
            "profile": dumps_str(user.profile),
            "login_count": str(user.login_count),
        }

        if user.created_at:
            data["created_at"] = user.created_at.isoformat()
        if user.updated_at:
            data["updated_at"] = user.updated_at.isoformat()
        if user.last_login_at:
            data["last_login_at"] = user.last_login_at.isoformat()

        return data

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
        """Cache a new user entry.

        .. note::
            Redis is typically used as a read-through cache.  For persistent
            primary storage use :class:`SQLUserStore` or :class:`MongoDBUserStore`.
        """
        import uuid

        user_id = str(uuid.uuid4())

        user = User(
            user_id=user_id,
            name=name,
            email=email,
            roles=list(roles or []),
            permissions=list(permissions or []),
            profile=profile or {},
        )

        key = await self._user_key(user_id)
        data = await self._data_from_user(user)
        # Store credential fields alongside other fields in the same hash
        if hashed_password:
            data["hashed_password"] = hashed_password
        data["previous_passwords"] = dumps_str([])

        await self.db_provider.redis.hset(key, mapping=data)  # type: ignore[attr-defined]
        if self.ttl is not None:
            await self.db_provider.redis.expire(key, self.ttl)  # type: ignore[attr-defined]

        logger.info("Cached user: %s", name)
        return user

    async def get_user_by_id(self, user_id: str) -> User | None:
        """Get user by ID"""
        key = await self._user_key(user_id)
        data = await self.db_provider.redis.hgetall(key)  # type: ignore[attr-defined]

        if not data:
            return None

        str_data = {
            k.decode() if isinstance(k, bytes) else k: (
                v.decode() if isinstance(v, bytes) else v
            )
            for k, v in data.items()
        }

        return await self._user_from_data(str_data)

    async def get_user_by_email(self, email: str) -> User | None:
        """Not supported — Redis does not index by email efficiently.

        .. warning::
            This always raises :exc:`NotImplementedError`.  Use the primary
            relational/document store for email-based lookups.
        """
        raise NotImplementedError(
            "RedisUserStore (CachedUserStore) does not support email lookups. "
            "Use the primary UserStoreProtocol for get_user_by_email.",
        )

    async def update_user(self, user: User) -> None:
        """Update non-credential fields for the cached user entry."""
        key = await self._user_key(user.user_id)
        data = await self._data_from_user(user)

        await self.db_provider.redis.hset(key, mapping=data)  # type: ignore[attr-defined]
        if self.ttl is not None:
            await self.db_provider.redis.expire(key, self.ttl)  # type: ignore[attr-defined]

        logger.info("Updated cached user: %s", user.name)

    async def delete_user(self, user_id: str) -> None:
        """Delete a user"""
        key = await self._user_key(user_id)
        await self.db_provider.redis.delete(key)  # type: ignore[attr-defined]

        logger.info("Deleted cached user: %s", user_id)

    async def list_users(self, skip: int = 0, limit: int = 100) -> list[User]:
        """Not supported — Redis is not designed for full user enumeration.

        .. warning::
            Always raises :exc:`NotImplementedError`.  Use the primary
            relational/document store for listing users.
        """
        raise NotImplementedError(
            "RedisUserStore (CachedUserStore) does not support list_users. "
            "Use the primary UserStoreProtocol for enumeration operations.",
        )

    async def count_users(self) -> int:
        """Not supported — Redis is not designed for counting all users.

        .. warning::
            Always raises :exc:`NotImplementedError`.  Use the primary
            relational/document store for count operations.
        """
        raise NotImplementedError(
            "RedisUserStore (CachedUserStore) does not support count_users. "
            "Use the primary UserStoreProtocol for enumeration operations.",
        )

    async def get_credentials(self, user_id: str) -> UserCredentials | None:
        """Return cached credential data for *user_id*.

        Returns ``None`` if the user entry is not in the cache.
        """
        key = await self._user_key(user_id)
        data = await self.db_provider.redis.hgetall(key)  # type: ignore[attr-defined]
        if not data:
            return None
        str_data = {
            k.decode() if isinstance(k, bytes) else k: (
                v.decode() if isinstance(v, bytes) else v
            )
            for k, v in data.items()
        }
        return UserCredentials(
            user_id=str_data.get("id", user_id),
            hashed_password=str_data.get("hashed_password"),
            previous_hashes=loads(str_data.get("previous_passwords", "[]")),
        )

    async def update_credentials(self, creds: UserCredentials) -> None:
        """Update credential fields in the cached user hash."""
        key = await self._user_key(creds.user_id)
        data: dict[str, str] = {
            "previous_passwords": dumps_str(creds.previous_hashes),
        }
        if creds.hashed_password is not None:
            data["hashed_password"] = creds.hashed_password

        await self.db_provider.redis.hset(key, mapping=data)  # type: ignore[attr-defined]
        if self.ttl is not None:
            await self.db_provider.redis.expire(key, self.ttl)  # type: ignore[attr-defined]

        logger.info("Updated cached credentials for user: %s", creds.user_id)


__all__ = ["MongoDBUserStore", "RedisUserStore", "SQLUserStore"]
