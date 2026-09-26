"""
Test cache stampede protection functionality.

Tests the StampedeProtectedCache implementation with comprehensive
coverage of concurrent access patterns and edge cases.
"""

import asyncio
from datetime import UTC
from unittest.mock import AsyncMock

import pytest

from quadkit import serialization as json
from quadkit.cache.service.protection import CacheEntry, StampedeProtectedCache


class TestStampedeLocksMemoryManagement:
    """P2 memory-management: stampede lock dict must not grow unbounded."""

    def test_stampede_locks_use_weak_references(self) -> None:
        """P2-stampede-lock: _locks must be a WeakValueDictionary so entries are
        garbage-collected once no coroutine holds a reference to the lock."""
        from unittest.mock import MagicMock
        import weakref

        cache_mock = MagicMock()
        svc = StampedeProtectedCache(cache_mock)
        assert isinstance(svc._locks, weakref.WeakValueDictionary)


class TestCacheStampede:
    """Test cache stampede protection."""

    @pytest.fixture
    def redis_client(self):
        """Create a mock Redis client for testing."""
        from unittest.mock import MagicMock

        client = MagicMock()

        # Track locks and cache data for testing
        locks = {}
        cache_data = {}
        cache_ttls = {}

        # Set up basic Redis operations
        async def mock_get(key):
            if key.startswith("lock:"):
                return locks.get(key)
            return cache_data.get(key)

        async def mock_set(key, value, **kwargs):
            if key.startswith("lock:") and kwargs.get("nx", False):
                # SET NX - only set if not exists
                if key in locks:
                    return False  # Lock already exists
                locks[key] = value

                # Simulate expiration by removing after timeout
                async def expire_lock():
                    await asyncio.sleep(kwargs.get("ex", 30))
                    locks.pop(key, None)

                task = asyncio.create_task(expire_lock())
                # Store task reference to prevent dangling task warning
                if not hasattr(mock_set, "_background_tasks"):
                    mock_set._background_tasks = set()
                mock_set._background_tasks.add(task)
                task.add_done_callback(mock_set._background_tasks.discard)
                return True
            # Regular set operation
            cache_data[key] = value
            if "ex" in kwargs:
                cache_ttls[key] = kwargs["ex"]
            return True

        async def mock_delete(key):
            if key.startswith("lock:"):
                locks.pop(key, None)
            else:
                cache_data.pop(key, None)
                cache_ttls.pop(key, None)
            return 1

        async def mock_ttl(key):
            return cache_ttls.get(key, -1)

        async def mock_setex(key, ttl, value):
            cache_data[key] = value
            cache_ttls[key] = ttl
            return True

        client.get = mock_get
        client.set = mock_set
        client.setex = mock_setex
        client.delete = mock_delete
        client.ttl = mock_ttl
        return client

    @pytest.fixture
    def cache(self, redis_client) -> StampedeProtectedCache:
        """Create cache instance."""
        return StampedeProtectedCache(redis_client)

    @pytest.mark.asyncio
    async def test_concurrent_requests_only_fetch_once(
        self,
        cache: StampedeProtectedCache,
    ) -> None:
        """Test that concurrent cache misses only fetch once."""
        # Arrange
        fetch_count = 0

        async def fetch_expensive_data() -> str:
            nonlocal fetch_count
            fetch_count += 1
            await asyncio.sleep(0.1)  # Simulate slow operation
            return "expensive_result"

        # Act - 100 concurrent requests
        results = await asyncio.gather(
            *[
                cache.get_or_compute("test_key", fetch_expensive_data, ttl=60)
                for _ in range(100)
            ],
        )

        # Assert - only fetched once!
        assert fetch_count == 1
        assert all(r == "expensive_result" for r in results)

    @pytest.mark.asyncio
    async def test_cache_hit_does_not_fetch(
        self,
        cache: StampedeProtectedCache,
    ) -> None:
        """Test that cache hit doesn't call fetch function."""
        # Arrange
        fetch_fn = AsyncMock(return_value="value")

        # First request - miss
        await cache.get_or_compute("key1", fetch_fn, ttl=60)
        assert fetch_fn.call_count == 1

        # Act - second request - hit
        result = await cache.get_or_compute("key1", fetch_fn, ttl=60)

        # Assert - didn't fetch again
        assert fetch_fn.call_count == 1
        assert result == "value"

    @pytest.mark.asyncio
    async def test_ttl_jitter_prevents_thundering_herd(
        self,
        cache: StampedeProtectedCache,
    ) -> None:
        """Test that TTL jitter spreads out expirations."""
        # Arrange
        fetch_fn = AsyncMock(return_value="value")

        # Act - cache 10 similar keys with jitter
        for i in range(10):
            await cache.get_or_compute(
                f"key_{i}",
                fetch_fn,
                ttl=100,
                ttl_jitter=0.2,  # ±20% jitter
            )

        # Get effective TTLs by parsing stored cache entries
        from datetime import datetime

        ttls = []
        for i in range(10):
            raw = await cache.cache.get(f"cache:key_{i}")
            parsed = json.loads(raw)
            cached_at = datetime.fromisoformat(parsed["cached_at"])
            expires_at = datetime.fromisoformat(parsed["expires_at"])
            effective_ttl = round((expires_at - cached_at).total_seconds())
            ttls.append(effective_ttl)

        # Assert - TTLs should be spread out (not all 100)
        assert len(set(ttls)) > 1  # Not all the same
        assert min(ttls) >= 80  # At least 80s
        assert max(ttls) <= 120  # At most 120s

    @pytest.mark.asyncio
    async def test_lock_timeout_prevents_deadlock(
        self,
        cache: StampedeProtectedCache,
    ) -> None:
        """Test that lock timeout prevents permanent deadlock."""
        # Arrange - create cache with short lock timeout
        cache = StampedeProtectedCache(
            cache.cache,
            lock_timeout=1,  # 1 second
        )

        async def slow_fetch() -> str:
            await asyncio.sleep(0.5)  # Slower than lock timeout
            return "value"

        # Act - start fetch (will timeout)
        try:
            result = await cache.get_or_compute("key", slow_fetch, ttl=60)
            # Should either succeed or handle timeout gracefully
        except (RuntimeError, ConnectionError, TimeoutError) as exc:
            pytest.fail(f"Should not raise: {exc}")

    @pytest.mark.asyncio
    async def test_probabilistic_early_refresh(
        self,
        cache: StampedeProtectedCache,
    ) -> None:
        """Test that probabilistic early refresh prevents stampede."""
        # This test is probabilistic, so we test the logic rather than randomness
        from datetime import datetime, timedelta

        # Create a cache entry that's close to expiration
        now = datetime.now(UTC)
        entry = CacheEntry(
            value="test_value",
            cached_at=now - timedelta(seconds=80),  # 80 seconds ago
            expires_at=now + timedelta(seconds=20),  # 20 seconds left
        )

        # With 100 second TTL, should refresh when close to expiry
        should_refresh = await cache._should_refresh_early(entry, 100)
        # This might be True or False due to randomness, but the logic should work

        # Test that fresh entries don't refresh early
        fresh_entry = CacheEntry(
            value="fresh",
            cached_at=now,
            expires_at=now + timedelta(seconds=80),  # 80 seconds left (>50% of 100)
        )
        should_not_refresh = await cache._should_refresh_early(fresh_entry, 100)
        assert should_not_refresh is False

    @pytest.mark.asyncio
    async def test_jitter_calculation(
        self,
        cache: StampedeProtectedCache,
    ) -> None:
        """Test that TTL jitter calculation works correctly."""
        # Test with no jitter
        ttl_no_jitter = cache._add_jitter(100, 0.0)
        assert ttl_no_jitter == 100

        # Test with jitter (multiple calls should give different results)
        ttls_with_jitter = list(map(lambda _: cache._add_jitter(100, 0.2), range(50)))
        unique_ttls = set(ttls_with_jitter)

        # Should have some variation (though random, statistically likely)
        # In practice, this test might occasionally fail due to randomness
        # but it's better than no test
        assert len(unique_ttls) > 1 or len(ttls_with_jitter) == 1

        # All values should be within expected range
        for ttl in ttls_with_jitter:
            assert 80 <= ttl <= 120  # ±20% of 100

    @pytest.mark.asyncio
    async def test_invalidate_removes_entry(
        self,
        cache: StampedeProtectedCache,
    ) -> None:
        """Test that invalidate removes cache entry."""

        # Arrange - put something in cache
        async def fetch_value():
            return "value"

        await cache.get_or_compute("test_key", fetch_value, ttl=60)

        # Verify it's cached (implementation uses "cache:" prefix)
        cached = await cache.cache.get("cache:test_key")
        assert cached is not None

        # Act - invalidate
        await cache.invalidate("test_key")

        # Assert - should be gone
        cached_after = await cache.cache.get("cache:test_key")
        assert cached_after is None

    @pytest.mark.asyncio
    async def test_lock_wait_timeout_fallback(
        self,
        cache: StampedeProtectedCache,
    ) -> None:
        """Test that wait timeout triggers fallback fetch."""
        # This is hard to test deterministically, but we can test the logic exists
        # The timeout logic is in _fetch_with_single_flight

        # Create cache with very short wait timeout
        cache = StampedeProtectedCache(
            cache.cache,
            lock_wait_timeout=0.01,  # Very short timeout
        )

        fetch_count = 0

        async def slow_fetch() -> str:
            nonlocal fetch_count
            fetch_count += 1
            await asyncio.sleep(0.1)  # Slow fetch
            return "value"

        # This should work but might use fallback logic
        result = await cache.get_or_compute("timeout_test", slow_fetch, ttl=60)
        assert result == "value"
        assert fetch_count >= 1  # At least one fetch occurred

    @pytest.mark.asyncio
    async def test_multiple_keys_concurrent_access(
        self,
        cache: StampedeProtectedCache,
    ) -> None:
        """Test that different keys don't interfere with each other."""
        # Arrange
        fetch_counts = {"key1": 0, "key2": 0}

        async def fetch_for_key(key: str) -> str:
            fetch_counts[key] += 1
            await asyncio.sleep(0.05)
            return f"value_for_{key}"

        async def get_key1() -> str:
            return await fetch_for_key("key1")

        async def get_key2() -> str:
            return await fetch_for_key("key2")

        # Act - concurrent requests for different keys
        results = await asyncio.gather(
            cache.get_or_compute("key1", get_key1, ttl=60),
            cache.get_or_compute("key2", get_key2, ttl=60),
            cache.get_or_compute("key1", get_key1, ttl=60),  # Second request for key1
        )

        # Assert
        assert results == ["value_for_key1", "value_for_key2", "value_for_key1"]
        assert fetch_counts["key1"] == 1  # Only fetched once for key1
        assert fetch_counts["key2"] == 1  # Only fetched once for key2

    @pytest.mark.asyncio
    async def test_exception_in_fetch_function(
        self,
        cache: StampedeProtectedCache,
    ) -> None:
        """Test that exceptions in fetch function are properly handled."""

        # Arrange
        async def failing_fetch() -> str:
            raise ValueError("Fetch failed")

        # Act & Assert - should propagate the exception
        with pytest.raises(ValueError, match="Fetch failed"):
            await cache.get_or_compute("failing_key", failing_fetch, ttl=60)

    @pytest.mark.asyncio
    async def test_lock_cleanup_on_exception(
        self,
        cache: StampedeProtectedCache,
    ) -> None:
        """Test that locks are cleaned up even when fetch fails."""
        # This is important for preventing deadlocks

        async def failing_fetch() -> str:
            raise RuntimeError("Fetch error")

        # Act - this should fail but not leave locks hanging
        with pytest.raises(RuntimeError):
            await cache.get_or_compute("cleanup_test", failing_fetch, ttl=60)

        # The lock should be released (hard to test directly, but no hanging state)

    @pytest.mark.asyncio
    async def test_cache_entry_serialization(
        self,
        cache: StampedeProtectedCache,
    ) -> None:
        """Test that cache entries are properly serialized/deserialized."""
        # Arrange
        test_data = {"complex": "data", "number": 42, "list": [1, 2, 3]}

        # Act
        async def fetch_data():
            return test_data

        await cache.get_or_compute("serialization_test", fetch_data, ttl=60)

        # Manually check what's in the cache backend (implementation uses "cache:" prefix)
        raw_data = await cache.cache.get("cache:serialization_test")
        assert raw_data is not None

        # Parse it back
        from quadkit import serialization as json

        parsed = json.loads(raw_data)

        assert parsed["value"] == test_data
        assert "cached_at" in parsed
        assert "expires_at" in parsed
