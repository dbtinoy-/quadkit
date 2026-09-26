"""Persistent token revocation store backed by a CacheBackendProtocol.

Revocation entries are stored in the cache with a configurable TTL so that
revocations survive process restarts and are visible across all nodes in a
distributed deployment.

Key format: ``quadkit:auth:revoked:{token_id}``

Example::

    from quadkit.auth.authn.revocation import PersistentTokenRevocationStore

    store = PersistentTokenRevocationStore(cache=my_cache_backend, ttl=3600)
    await store.revoke("tok_abc123", expires_at=token.expires_at)
    revoked = await store.is_revoked("tok_abc123")
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from quadkit.logging import get_logger
from quadkit.primitives import clock as ambient_clock

if TYPE_CHECKING:
    from quadkit.contracts.infra.cache.protocols import CacheBackendProtocol

__all__ = ["PersistentTokenRevocationStore"]

logger = get_logger(__name__)

_KEY_PREFIX = "quadkit:auth:revoked:"
_DEFAULT_TTL = 86400  # 24 hours


class PersistentTokenRevocationStore:
    """Persistent token revocation list backed by a :class:`CacheBackendProtocol`.

    Stores revoked token IDs in the cache so that revocations survive process
    restarts and are consistent across all nodes in a distributed deployment.

    A sentinel value (``"1"``) is written under
    ``quadkit:auth:revoked:{token_id}`` with the configured TTL.  When
    ``expires_at`` is provided to :meth:`revoke`, the TTL is capped to the
    token's remaining lifetime so stale entries are not kept longer than needed.

    Args:
        cache: Cache backend used to persist revoked token identifiers.
        ttl:   Default expiry in seconds for revocation records.
               Defaults to ``86400`` (24 h).
    """

    def __init__(
        self,
        cache: CacheBackendProtocol,
        ttl: int = _DEFAULT_TTL,
    ) -> None:
        self._cache = cache
        self._ttl = ttl

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _make_key(self, token_id: str) -> str:
        """Return the cache key for a token ID."""
        return f"{_KEY_PREFIX}{token_id}"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def revoke(
        self,
        token_id: str,
        expires_at: datetime | None = None,
    ) -> None:
        """Mark *token_id* as revoked.

        If the token is already expired (``expires_at`` is in the past) the
        call is a no-op — there is no point persisting an entry for a token
        that the signature validation layer will reject on its own.

        Args:
            token_id:   Unique identifier of the JWT/opaque token to revoke.
            expires_at: Optional token expiry time.  Used to compute a shorter
                        TTL so the cache entry is not held longer than the
                        token's own lifetime.
        """
        ttl = self._ttl

        if expires_at is not None:
            # Normalise to UTC-aware datetime for safe arithmetic.
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)
            now = ambient_clock.now()
            remaining = int((expires_at - now).total_seconds())
            if remaining <= 0:
                logger.debug(
                    "token_revocation_skipped_already_expired",
                    token_id=token_id,
                )
                return
            ttl = min(ttl, remaining)

        key = self._make_key(token_id)
        await self._cache.set(key, "1", ttl=ttl)
        logger.info("token_revoked", token_id=token_id, ttl=ttl)

    async def is_revoked(self, token_id: str) -> bool:
        """Return ``True`` if *token_id* is present in the revocation list.

        Args:
            token_id: The token identifier to check.

        Returns:
            ``True`` when the token has been explicitly revoked and the
            revocation entry has not yet expired, ``False`` otherwise.
        """
        value = await self._cache.get(self._make_key(token_id))
        return value is not None
