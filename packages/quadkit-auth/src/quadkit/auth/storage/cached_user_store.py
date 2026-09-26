"""Cached user store implementation for performance optimization"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any, cast

from quadkit.auth.models.user import User, UserCredentials
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.auth.storage.token_store import UserStoreProtocol
    from quadkit.contracts.events.protocols import PubSubProtocol
    from quadkit.contracts.infra.cache import CacheBackendProtocol

logger = get_logger(__name__)

#: PubSubProtocol topic on which user-cache invalidation events are broadcast.
CACHE_INVALIDATION_TOPIC = "auth.user.cache.invalidate"


class CachedUserStore:
    """User store with multi-layer caching for high-performance user lookups.

    Implements a two-layer caching strategy:
    - L1: In-memory cache (ultra-fast, short-lived)
    - L2: Distributed cache (Redis, etc., longer-lived)

    This dramatically reduces database load for authentication middleware.
    """

    def __init__(
        self,
        user_store: UserStoreProtocol,
        cache_service: CacheBackendProtocol,
        cache_ttl: int = 300,  # 5 minutes
        memory_cache_ttl: int = 60,  # 1 minute in memory
        *,
        pubsub: PubSubProtocol | None = None,
    ):
        """Initialize cached user store.

        Args:
            user_store: Underlying user store implementation.
            cache_service: Cache service for distributed caching.
            cache_ttl: TTL for distributed cache in seconds.
            memory_cache_ttl: TTL for in-memory cache in seconds.
            pubsub: Optional :class:`~quadkit.contracts.events.protocols.PubSubProtocol`
                backend used for cross-instance cache invalidation.  When
                provided, :meth:`update_user` and :meth:`delete_user` publish
                an invalidation event to :data:`CACHE_INVALIDATION_TOPIC`
                so that all other running instances can evict their L1 caches.
                Call :meth:`subscribe_to_invalidations` once at startup to
                respond to those events on *this* instance.
        """
        self.user_store = user_store
        self.cache_service = cache_service
        self.cache_ttl = cache_ttl
        self.memory_cache_ttl = memory_cache_ttl
        self._pubsub: PubSubProtocol | None = pubsub

        # In-memory L1 cache: {cache_key: {"user": User, "expires_at": timestamp}}
        self._memory_cache: dict[str, dict[str, Any]] = {}

    async def subscribe_to_invalidations(self) -> None:
        """Subscribe to cross-instance cache invalidation events.

        Should be called once during application startup when a
        :class:`~quadkit.contracts.events.protocols.PubSubProtocol` backend is
        configured.  Each received event evicts the affected user from
        the in-process L1 cache so stale data is never served.

        A no-op if no pubsub backend was provided.
        """
        if self._pubsub is None:
            return
        await self._pubsub.subscribe(
            CACHE_INVALIDATION_TOPIC, self._handle_invalidation
        )
        logger.info(
            "cached_user_store.subscribed",
            topic=CACHE_INVALIDATION_TOPIC,
        )

    async def _handle_invalidation(self, data: Any) -> None:
        """Handle a ``user.cache.invalidate`` event from another instance.

        Evicts the in-process L1 cache entries for the affected user.

        Args:
            data: Event payload.  Expected to include a ``user_id``
                field and optionally ``email`` and ``name`` fields.
        """
        if not isinstance(data, dict):
            return
        user_id: str | None = data.get("user_id")
        email: str | None = data.get("email")
        name: str | None = data.get("name")

        evicted: list[str] = []
        for key in (
            f"user:id:{user_id}" if user_id else None,
            f"user:email:{email}" if email else None,
            f"user:name:{name}" if name else None,
        ):
            if key and self._memory_cache.pop(key, None) is not None:
                evicted.append(key)

        if evicted:
            logger.debug(
                "cached_user_store.l1_evicted_remote",
                keys=evicted,
                user_id=user_id,
            )

    async def get_user_by_id(self, user_id: str) -> User | None:
        """Get user by ID with multi-layer caching.

        Returns:
            User object if found, None otherwise
        """
        cache_key = f"user:id:{user_id}"

        # L1: Check in-memory cache
        cached = self._memory_cache.get(cache_key)
        if cached and cached["expires_at"] > time.monotonic():
            logger.debug("L1 cache HIT for user ID: %s", user_id)

            return cast("User", cached["user"])

        # L2: Check distributed cache
        cached_result = await self.cache_service.get(cache_key)
        cached_data = (
            cached_result.unwrap()
            if hasattr(cached_result, "is_ok") and cached_result.is_ok()
            else cached_result
            if cached_result
            else None
        )
        if cached_data:
            logger.debug("L2 cache HIT for user ID: %s", user_id)
            user = self._deserialize_user(cached_data)  # type: ignore[arg-type]

            # Store in L1 cache
            self._memory_cache[cache_key] = {
                "user": user,
                "expires_at": time.monotonic() + self.memory_cache_ttl,
            }

            return user

        # Cache MISS: Fetch from database
        logger.debug("Cache MISS for user ID: %s", user_id)
        db_user: User | None = await self.user_store.get_user_by_id(user_id)

        if db_user:
            # Store in distributed cache (L2)
            await self.cache_service.set(
                cache_key,
                self._serialize_user(db_user),
                ttl=self.cache_ttl,
            )

            # Store in memory cache (L1)
            self._memory_cache[cache_key] = {
                "user": db_user,
                "expires_at": time.monotonic() + self.memory_cache_ttl,
            }

        return db_user

    async def get_user_by_email(self, email: str) -> User | None:
        """Get user by email with caching.

        Note: Email lookups are less cacheable than ID lookups since
        emails can change, but we still cache them for performance.
        """
        cache_key = f"user:email:{email}"

        # L1: Check in-memory cache
        cached = self._memory_cache.get(cache_key)
        if cached and cached["expires_at"] > time.monotonic():
            logger.debug("L1 cache HIT for email: %s", email)

            return cast("User", cached["user"])

        # L2: Check distributed cache
        cached_result = await self.cache_service.get(cache_key)
        cached_data = (
            cached_result.unwrap()
            if hasattr(cached_result, "is_ok") and cached_result.is_ok()
            else cached_result
            if cached_result
            else None
        )
        if cached_data:
            logger.debug("L2 cache HIT for email: %s", email)
            user = self._deserialize_user(cached_data)  # type: ignore[arg-type]

            # Store in L1 cache
            self._memory_cache[cache_key] = {
                "user": user,
                "expires_at": time.monotonic() + self.memory_cache_ttl,
            }

            return user

        # Cache MISS: Fetch from database
        logger.debug("Cache MISS for email: %s", email)
        db_user: User | None = await self.user_store.get_user_by_email(email)

        if db_user:
            # Store in both caches
            await self.cache_service.set(
                cache_key,
                self._serialize_user(db_user),
                ttl=self.cache_ttl,
            )

            self._memory_cache[cache_key] = {
                "user": db_user,
                "expires_at": time.monotonic() + self.memory_cache_ttl,
            }

        return db_user

    async def update_user(self, user: User) -> None:
        """Update user and invalidate all related caches."""
        # Update the underlying store
        await self.user_store.update_user(user)

        # Invalidate all caches for this user
        user_id = user.user_id
        name = user.name
        email = user.email

        cache_keys = [
            f"user:id:{user_id}",
            f"user:name:{name}",
            f"user:email:{email}",
        ]

        # Invalidate L1 cache
        for key in cache_keys:
            self._memory_cache.pop(key, None)

        # Invalidate L2 cache
        await self.cache_service.delete_many(cache_keys)

        logger.debug("Cache INVALIDATE for user: %s", user_id)

        # Broadcast cross-instance invalidation event
        if self._pubsub is not None:
            await self._pubsub.publish(
                CACHE_INVALIDATION_TOPIC,
                {"user_id": user_id, "email": email, "name": name},
            )

    async def delete_user(self, user_id: str) -> None:
        """Delete user and invalidate caches."""
        # Get user info before deletion for cache invalidation
        user = await self.get_user_by_id(user_id)
        if user:
            # Delete from underlying store
            await self.user_store.delete_user(user_id)

            # Invalidate caches
            cache_keys = [
                f"user:id:{user_id}",
                f"user:name:{user.name}",
                f"user:email:{user.email}",
            ]

            for key in cache_keys:
                self._memory_cache.pop(key, None)

            await self.cache_service.delete_many(cache_keys)

            logger.debug("Cache INVALIDATE for deleted user: %s", user_id)

            # Broadcast cross-instance invalidation event
            if self._pubsub is not None:
                await self._pubsub.publish(
                    CACHE_INVALIDATION_TOPIC,
                    {"user_id": user_id, "email": user.email, "name": user.name},
                )
        else:
            # User not found, just delete from underlying store
            await self.user_store.delete_user(user_id)

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
        """Create user (no caching needed for new users)."""
        return await self.user_store.create_user(
            name=name,
            email=email,
            hashed_password=hashed_password,
            roles=roles,
            permissions=permissions,
            profile=profile,
            **kwargs,
        )

    async def list_users(self, skip: int = 0, limit: int = 100) -> list[User]:
        """List users (not cached for simplicity)."""
        return await self.user_store.list_users(skip, limit)

    async def count_users(self) -> int:
        """Count users (not cached for simplicity)."""
        return await self.user_store.count_users()

    async def get_credentials(self, user_id: str) -> UserCredentials | None:
        """Return credential data from the underlying store.

        Credentials are never cached — they are always read from the
        primary store to ensure the latest password hash is used.
        """
        return await self.user_store.get_credentials(user_id)

    async def update_credentials(self, creds: UserCredentials) -> None:
        """Persist updated credentials and invalidate the user cache."""
        await self.user_store.update_credentials(creds)
        # Invalidate the cached user entry so the next read reflects any
        # side-effects the underlying store may have applied.
        cache_key = f"user:id:{creds.user_id}"
        self._memory_cache.pop(cache_key, None)
        await self.cache_service.delete_many([cache_key])

    def _serialize_user(self, user: User) -> dict[str, Any]:
        """Serialize user for caching (credential fields excluded)."""
        return {
            "id": user.user_id,
            "name": user.name,
            "email": user.email,
            "is_active": user.is_active,
            "is_verified": user.is_verified,
            "roles": user.roles,
            "permissions": user.permissions,
            "profile": user.profile,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "updated_at": user.updated_at.isoformat() if user.updated_at else None,
            "last_login_at": user.last_login_at.isoformat()
            if user.last_login_at
            else None,
            "login_count": user.login_count,
        }

    def _deserialize_user(self, data: dict[str, Any]) -> User:
        """Deserialize user from cache (credential fields excluded)."""
        from datetime import datetime

        def parse_dt(val: Any) -> datetime | None:
            if not val:
                return None
            if isinstance(val, datetime):
                return val
            try:
                return datetime.fromisoformat(str(val))
            except (ValueError, TypeError):
                return None

        return User(
            user_id=data["id"],
            name=data.get("name") or "",
            email=data["email"],
            is_active=data.get("is_active", True),
            is_verified=data.get("is_verified", False),
            roles=data.get("roles", []),
            permissions=data.get("permissions", []),
            profile=data.get("profile", {}),
            created_at=parse_dt(data.get("created_at")),
            updated_at=parse_dt(data.get("updated_at")),
            last_login_at=parse_dt(data.get("last_login_at")),
            login_count=data.get("login_count", 0),
        )


__all__ = ["CACHE_INVALIDATION_TOPIC", "CachedUserStore"]
