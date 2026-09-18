"""Token blacklist protocol.

Defines the contract for token blacklist implementations used to
invalidate JWT tokens before their natural expiration time.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class TokenBlacklistProtocol(Protocol):
    """Protocol for token blacklist implementations.

    Implementations must support blacklisting tokens and checking whether
    a token has been blacklisted.  Concrete implementations may persist
    entries in Redis (via CacheBackendProtocol) or keep them in-process for
    environments that do not require distributed invalidation.

    Example::

        class RedisTokenBlacklist:
            async def blacklist(self, token: str, ttl: int | None = None) -> None:
                token_hash = hashlib.sha256(token.encode()).hexdigest()
                await self._cache.set(f"jwt:blacklist:{token_hash}", "1", ttl=ttl)

            async def is_blacklisted(self, token: str) -> bool:
                token_hash = hashlib.sha256(token.encode()).hexdigest()
                return await self._cache.exists(f"jwt:blacklist:{token_hash}")
    """

    async def blacklist(self, token: str, ttl: int | None = None) -> None:
        """Add a token to the blacklist.

        Args:
            token: The raw token string to blacklist.
            ttl: Time-to-live in seconds.  If None the entry persists
                indefinitely (only appropriate for in-memory stores).
        """
        ...

    async def is_blacklisted(self, token: str) -> bool:
        """Check whether a token is blacklisted.

        Args:
            token: The raw token string to check.

        Returns:
            ``True`` if the token is blacklisted, ``False`` otherwise.
        """
        ...


__all__ = ["TokenBlacklistProtocol"]
