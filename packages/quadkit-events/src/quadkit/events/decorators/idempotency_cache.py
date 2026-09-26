"""Bounded, TTL-respecting cache for the :func:`idempotent` decorator.

Replaces the former module-level ``_idempotency_cache`` dict: every
decorated function gets its own instance (no process-wide shared state),
entries expire after their TTL (time-sourced from the ambient clock so
tests can drive expiry with :class:`quadkit.testing.clock.FixedClock`),
and the cache is size-bounded, evicting least-recently-used entries once
``max_size`` is reached — expired entries first, mirroring
``MemoryStateStore`` in ``quadkit-cache``.
"""

from __future__ import annotations

from collections import OrderedDict
from typing import Any

from quadkit.primitives import clock as ambient_clock

MAX_IDEMPOTENCY_CACHE_SIZE = 10_000


class IdempotencyCache:
    """Bounded, TTL-respecting cache used by idempotent decorators.

    Entries are stored as ``(expires_at, value)`` pairs in insertion
    order; reads and writes reorder entries so the least-recently-used
    entry sits at the front and is evicted first when at capacity.

    Attributes:
        default_ttl: Fallback TTL in seconds when ``set`` is not given one.
        max_size: Maximum number of entries; beyond this the least
            recently used entry is evicted on write.
    """

    def __init__(
        self,
        default_ttl: float = 3600.0,
        max_size: int = MAX_IDEMPOTENCY_CACHE_SIZE,
    ) -> None:
        self.default_ttl = default_ttl
        self.max_size = max_size
        self._entries: OrderedDict[str, tuple[float, Any]] = OrderedDict()

    def get(self, key: str, default: Any = None) -> Any:
        """Return the cached value for ``key``, or ``default`` if absent.

        Expired entries are deleted lazily on access, so a value that
        has outlived its TTL is reported as a miss.  A cached ``None``
        value is returned as ``None`` — indistinguishable from a miss
        only in terms of the return value; the ``default`` argument
        distinguishes the two for callers that need to.

        Args:
            key: Cache key.
            default: Value returned when the key is missing or expired.

        Returns:
            The cached value, or ``default`` when missing or expired.
        """
        entry = self._entries.get(key)
        if entry is None:
            return default
        expires_at, value = entry
        if ambient_clock.timestamp() > expires_at:
            del self._entries[key]
            return default
        self._entries.move_to_end(key)
        return value

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        """Store ``value`` under ``key``, expiring after ``ttl`` seconds.

        When ``ttl`` is ``None`` the instance ``default_ttl`` applies.
        Re-setting an existing key refreshes its expiry and marks it
        most-recently-used.  A new key written at capacity evicts
        expired entries first, then the least-recently-used entry.

        Args:
            key: Cache key.
            value: Value to cache (any picklable-free Python object).
            ttl: Time-to-live in seconds; ``None`` uses ``default_ttl``.
        """
        expires_at = ambient_clock.timestamp() + (
            ttl if ttl is not None else self.default_ttl
        )
        if key in self._entries:
            self._entries[key] = (expires_at, value)
            self._entries.move_to_end(key)
            return
        if len(self._entries) >= self.max_size:
            self._evict_expired()
            if len(self._entries) >= self.max_size:
                self._entries.popitem(last=False)
        self._entries[key] = (expires_at, value)

    def clear(self) -> None:
        """Remove all entries from the cache."""
        self._entries.clear()

    def _evict_expired(self) -> None:
        """Delete every expired entry in place."""
        now = ambient_clock.timestamp()
        expired = [
            k for k, (expires_at, _) in self._entries.items() if now > expires_at
        ]
        for key in expired:
            del self._entries[key]
