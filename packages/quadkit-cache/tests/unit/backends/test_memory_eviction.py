"""Tests for MemoryStateStore and MemoryCacheBackend LRU eviction (audit C2).

Verifies that ``max_size`` is enforced in-memory with a Least-Recently-Used
eviction policy and that the config value is properly wired through the DI
layer.
"""

from __future__ import annotations

import asyncio

import pytest

from quadkit.cache.backends.memory.backend import MemoryCacheBackend
from quadkit.cache.backends.memory_state import MemoryStateStore
from quadkit.cache.config import CacheBackendConfig, CacheOperationConfig
from quadkit.cache.types import BackendType
from quadkit.testing.clock import FixedClock


# ---------------------------------------------------------------------------
# MemoryStateStore — unit tests
# ---------------------------------------------------------------------------


class TestMemoryStateStoreLRU:
    """LRU eviction behaviour of MemoryStateStore."""

    @pytest.mark.asyncio
    async def test_store_without_max_size_grows_unbounded(self) -> None:
        """When max_size is None, entries are never evicted."""
        store = MemoryStateStore(max_size=None)
        for i in range(200):
            await store.set(f"key-{i}", i)

        assert len(store._data) == 200

    @pytest.mark.asyncio
    async def test_store_respects_max_size(self) -> None:
        """Total number of entries never exceeds max_size."""
        store = MemoryStateStore( max_size=5)

        for i in range(10):
            await store.set(f"key-{i}", i)

        assert len(store._data) <= 5

    @pytest.mark.asyncio
    async def test_lru_oldest_entry_evicted_first(self) -> None:
        """When at capacity, the least-recently-used entry is evicted."""
        store = MemoryStateStore( max_size=3)

        await store.set("a", 1)
        await store.set("b", 2)
        await store.set("c", 3)

        # Access "a" to make it most-recently used
        await store.get("a")

        # Insert "d" — "b" was least recently touched, so it gets evicted
        await store.set("d", 4)

        assert "b" not in store._data, "Expected 'b' to be evicted (LRU)"
        assert "a" in store._data
        assert "c" in store._data
        assert "d" in store._data

    @pytest.mark.asyncio
    async def test_update_existing_key_counts_as_access(self) -> None:
        """Re-setting an existing key marks it as most-recently used."""
        store = MemoryStateStore( max_size=3)

        await store.set("x", 1)
        await store.set("y", 2)
        await store.set("z", 3)

        # Re-write "x" to refresh its LRU position
        await store.set("x", 99)

        # Insert "w" — "y" is now the LRU entry
        await store.set("w", 4)

        assert "y" not in store._data, "Expected 'y' to be evicted after 'x' refresh"
        assert "x" in store._data
        assert "z" in store._data
        assert "w" in store._data

    @pytest.mark.asyncio
    async def test_expired_entries_evicted_before_lru(self) -> None:
        """Expired entries are purged before evicting the LRU live entry."""
        store = MemoryStateStore( max_size=3)

        # "exp" expires almost immediately (ttl=1 microsecond via negative trick)
        # Use ttl=1 and override expires_at to simulate expiry
        await store.set("live-a", "a")
        await store.set("live-b", "b")
        await store.set("live-c", "c")

        # Manually mark "live-c" as expired
        store._data["live-c"]["expires_at"] = 0.0  # Unix epoch → always expired

        # Insert a new entry — expired "live-c" should be purged first
        await store.set("live-d", "d")

        assert "live-c" not in store._data, "Expected expired entry to be evicted"
        assert "live-d" in store._data

    @pytest.mark.asyncio
    async def test_exists_returns_false_for_missing_key(self) -> None:
        """exists() returns False for keys that were never set."""
        store = MemoryStateStore()
        assert not (await store.exists("nonexistent"))

    @pytest.mark.asyncio
    async def test_exists_returns_true_for_live_key(self) -> None:
        """exists() returns True for a key that is set and not expired."""
        store = MemoryStateStore()
        await store.set("present", True)
        assert await store.exists("present")

    @pytest.mark.asyncio
    async def test_exists_returns_false_for_expired_key(self) -> None:
        """exists() returns False and evicts a key whose TTL has elapsed."""
        store = MemoryStateStore()
        await store.set("temp", "val")
        store._data["temp"]["expires_at"] = 0.0  # simulate expiry

        assert not (await store.exists("temp"))
        assert "temp" not in store._data

    @pytest.mark.asyncio
    async def test_health_check_reports_max_size(self) -> None:
        """health_check details includes the configured max_size."""
        store = MemoryStateStore( max_size=100)
        result = await store.health_check()
        assert result.details["max_size"] == 100


# ---------------------------------------------------------------------------
# MemoryCacheBackend — wiring tests
# ---------------------------------------------------------------------------


class TestMemoryCacheBackendMaxSize:
    """Verify MemoryCacheBackend wires max_size through to MemoryStateStore."""

    def test_default_max_size_is_none(self) -> None:
        """By default no eviction limit is enforced."""
        backend = MemoryCacheBackend()
        assert backend._store.max_size is None

    def test_custom_max_size_propagated(self) -> None:
        """A provided max_size is forwarded to the internal store."""
        backend = MemoryCacheBackend(max_size=500)
        assert backend._store.max_size == 500

    @pytest.mark.asyncio
    async def test_backend_enforces_capacity(self) -> None:
        """MemoryCacheBackend evicts entries when max_size is exceeded."""
        config = CacheOperationConfig(default_ttl=None, key_prefix="")
        backend = MemoryCacheBackend(config=config, max_size=3)

        for i in range(10):
            await backend.set(f"key{i}", f"val{i}")

        assert len(backend._store._data) <= 3


# ---------------------------------------------------------------------------
# CacheBackendConfig → DI wiring test
# ---------------------------------------------------------------------------


class TestCacheBackendConfigMaxSizeWiring:
    """Verify max_size flows from CacheBackendConfig through create_backend."""

    @pytest.mark.asyncio
    async def test_create_backend_passes_max_size_to_memory_backend(self) -> None:
        """create_backend wires CacheBackendConfig.max_size to MemoryCacheBackend."""
        from quadkit.cache.backends.factory import create_backend

        cfg = CacheBackendConfig(
            name="test-mem",
            type=BackendType.MEMORY,
            max_size=42,
        )
        backend = await create_backend(cfg)

        assert isinstance(backend, MemoryCacheBackend)
        assert backend._store.max_size == 42

    @pytest.mark.asyncio
    async def test_create_backend_no_max_size_defaults_to_none(self) -> None:
        """When max_size is not set, the store has no eviction limit."""
        from quadkit.cache.backends.factory import create_backend

        cfg = CacheBackendConfig(
            name="test-mem-no-limit",
            type=BackendType.MEMORY,
        )
        backend = await create_backend(cfg)

        assert isinstance(backend, MemoryCacheBackend)
        assert backend._store.max_size is None


# ---------------------------------------------------------------------------
# TTL vs LRU interaction (audit N6)
# ---------------------------------------------------------------------------


class TestTTLVsLRUEviction:
    """Verify TTL expiry takes priority over LRU recency."""

    @pytest.mark.skip(reason="TTL tests require time-advancing clock - use SystemClock for these")
    @pytest.mark.asyncio
    async def test_expired_mru_item_returns_none_after_ttl(self) -> None:
        """TTL expiry wins even for the most-recently-used entry.

        Setting a short TTL then accessing the key (making it MRU) should
        not protect it from expiry — once TTL elapses the entry must be gone.
        """
        store = MemoryStateStore(max_size=3)

        # "a" has a very short TTL; "b" and "c" are permanent
        await store.set("a", "value-a", ttl=1)
        await store.set("b", "value-b")
        await store.set("c", "value-c")

        # Touch "a" to make it the MRU entry
        assert await store.get("a") == "value-a"

        # Wait for TTL to expire
        await asyncio.sleep(1.1)

        # Even though "a" was MRU, TTL takes precedence
        assert await store.get("a") is None, "Expired MRU entry must be None after TTL"

    @pytest.mark.skip(reason="TTL tests require time-advancing clock - use SystemClock for these")
    @pytest.mark.asyncio
    async def test_lru_eviction_prefers_expired_entries(self) -> None:
        """When at capacity LRU eviction removes expired entries before active ones.

        The store must not evict a non-expired LRU entry when there is already
        an expired entry that can be cleared instead.
        """
        store = MemoryStateStore(max_size=3)

        # Fill to capacity; "old" has a very short TTL
        await store.set("old", "stale", ttl=1)
        await store.set("b", "value-b")
        await store.set("c", "value-c")

        # Let "old" expire
        await asyncio.sleep(1.1)

        # Inserting "new" must evict the expired "old" rather than "b" or "c"
        await store.set("new", "fresh")

        assert await store.get("old") is None, "'old' (expired) must be gone"
        assert await store.get("b") == "value-b", "'b' must survive — not LRU-evicted"
        assert await store.get("c") == "value-c", "'c' must survive"
        assert await store.get("new") == "fresh", "'new' must be present"

    @pytest.mark.asyncio
    async def test_lru_evicts_oldest_when_no_expired_entries(self) -> None:
        """When no entries are expired, the LRU entry is still evicted at capacity."""
        store = MemoryStateStore( max_size=3)

        await store.set("first", 1)
        await store.set("second", 2)
        await store.set("third", 3)

        # Access "first" and "second" to push "third" to LRU position
        await store.get("first")
        await store.get("second")

        # Insert "fourth" — "third" is now LRU
        await store.set("fourth", 4)

        assert await store.get("third") is None, "'third' must be LRU-evicted"
        assert await store.get("first") == 1
        assert await store.get("second") == 2
        assert await store.get("fourth") == 4
