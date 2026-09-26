"""In-memory state store implementation"""

from __future__ import annotations

from collections import OrderedDict
from datetime import datetime
from typing import Any
from uuid import UUID

from quadkit.contracts import HealthCheckResult, HealthStatus, StateStoreProtocol
from quadkit.primitives import clock as ambient_clock
from quadkit.serialization import dumps, loads


class MemoryStateStore(StateStoreProtocol):
    """In-memory state store with optional LRU eviction.

    When *max_size* is provided the store enforces a capacity limit using a
    Least-Recently-Used (LRU) eviction policy: the entry that was least
    recently read **or** written is removed when the store is at capacity.
    When *max_size* is ``None`` the store grows without bound (suitable for
    tests and development; not recommended for production).
    """

    def __init__(self, max_size: int | None = None) -> None:
        """Initialise the state store.

        Args:
            max_size: Maximum number of entries to hold at once.  When the
                store is full and a new key is written the least-recently-used
                entry is evicted first.  ``None`` (default) disables eviction.
        """
        self.max_size = max_size
        # OrderedDict preserves insertion/access order for LRU tracking.
        self._data: OrderedDict[str, dict[str, Any]] = OrderedDict()

    def _serialize_value(self, value: Any) -> bytes:
        """Serialize value to JSON bytes with enhanced type support."""

        def encoder(obj: Any) -> Any:
            if isinstance(obj, datetime):
                return obj.isoformat()
            if isinstance(obj, UUID):
                return str(obj)
            if hasattr(obj, "__dict__"):
                return obj.__dict__
            return str(obj)

        return dumps(value, default=encoder)

    def _deserialize_value(self, value: bytes) -> Any:
        """Deserialize value from JSON bytes."""
        return loads(value)

    def _evict_expired(self) -> None:
        """Remove all expired entries in-place (single pass, no allocation)."""
        now = ambient_clock.timestamp()
        expired = [
            k
            for k, v in self._data.items()
            if v.get("expires_at") is not None and now > v["expires_at"]
        ]
        for k in expired:
            del self._data[k]

    async def get(self, key: str) -> Any | None:
        """Get a value by key, touching it as most-recently-used."""
        if key not in self._data:
            return None

        entry = self._data[key]
        now = ambient_clock.timestamp()
        if entry.get("expires_at") is not None and now > entry["expires_at"]:
            del self._data[key]
            return None

        # Move to end to mark as most-recently used
        if self.max_size is not None:
            self._data.move_to_end(key)

        return self._deserialize_value(entry["value"])

    async def set(self, key: str, value: Any, ttl: int | None = None) -> bool:  # type: ignore[override]
        """Set a value with optional TTL, evicting the LRU entry if at capacity."""
        now = ambient_clock.timestamp()
        expires_at = now + ttl if ttl else None
        serialized_value = self._serialize_value(value)

        if key in self._data:
            # Update existing entry and move to end (most recently used)
            self._data[key] = {"value": serialized_value, "expires_at": expires_at}
            if self.max_size is not None:
                self._data.move_to_end(key)
        else:
            # New entry — evict if at capacity
            if self.max_size is not None and len(self._data) >= self.max_size:
                # Try expired entries first; if none, evict the LRU (front)
                self._evict_expired()
                if len(self._data) >= self.max_size:
                    self._data.popitem(last=False)  # remove least-recently used

            self._data[key] = {"value": serialized_value, "expires_at": expires_at}

        return True

    async def delete(self, key: str) -> bool:
        """Delete a value by key."""
        existed = key in self._data
        self._data.pop(key, None)
        return existed

    async def exists(self, key: str) -> bool:
        """Check if a key exists and has not expired."""
        if key not in self._data:
            return False
        entry = self._data[key]
        now = ambient_clock.timestamp()
        if entry.get("expires_at") is not None and now > entry["expires_at"]:
            del self._data[key]
            return False
        return True

    async def clear(self) -> None:
        """Clear all values from the store."""
        self._data.clear()

    async def get_bulk(self, keys: list[str]) -> dict[str, Any]:
        """Get multiple values by keys."""
        result = {}
        for key in keys:
            value = await self.get(key)
            if value is not None:
                result[key] = value
        return result

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Check the health of the state store."""
        return HealthCheckResult(
            component="memory-state",
            status=HealthStatus.HEALTHY,
            details={
                "driver": "memory",
                "keys_count": len(self._data),
                "max_size": self.max_size,
            },
        )
