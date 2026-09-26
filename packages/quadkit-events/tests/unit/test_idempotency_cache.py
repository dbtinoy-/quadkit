"""Unit tests for IdempotencyCache — bounded, TTL-respecting cache."""

from __future__ import annotations

from datetime import UTC, datetime

from quadkit.events.decorators.idempotency_cache import IdempotencyCache
from quadkit.primitives import clock as ambient_clock
from quadkit.testing.clock import FixedClock

START = datetime(2026, 8, 18, 12, 0, 0, tzinfo=UTC)


class TestIdempotencyCacheTTL:
    """TTL expiry behaviour, driven by the ambient clock."""

    def test_get_returns_value_within_ttl(self) -> None:
        cache = IdempotencyCache()
        with ambient_clock.use(FixedClock(START)):
            cache.set("k", "v", ttl=3600)
            assert cache.get("k") == "v"

    def test_get_after_ttl_returns_default_and_evicts(self) -> None:
        cache = IdempotencyCache()
        fixed = FixedClock(START)
        with ambient_clock.use(fixed):
            cache.set("k", "v", ttl=3600)
            fixed.advance(3601)
            assert cache.get("k") is None
            assert "k" not in cache._entries

    def test_cached_none_value_is_not_a_miss(self) -> None:
        cache = IdempotencyCache()
        with ambient_clock.use(FixedClock(START)):
            cache.set("k", None, ttl=3600)
            assert cache.get("k", "missing") is None

    def test_no_ttl_uses_default_ttl(self) -> None:
        cache = IdempotencyCache(default_ttl=60.0)
        fixed = FixedClock(START)
        with ambient_clock.use(fixed):
            cache.set("k", "v")
            fixed.advance(59)
            assert cache.get("k") == "v"
            fixed.advance(2)
            assert cache.get("k") is None

    def test_custom_ttl_overrides_default(self) -> None:
        cache = IdempotencyCache(default_ttl=3600.0)
        fixed = FixedClock(START)
        with ambient_clock.use(fixed):
            cache.set("k", "v", ttl=10)
            fixed.advance(11)
            assert cache.get("k") is None


class TestIdempotencyCacheBounds:
    """Size bounding with LRU eviction (expired entries first)."""

    def test_entries_never_exceed_max_size(self) -> None:
        cache = IdempotencyCache(max_size=2)
        with ambient_clock.use(FixedClock(START)):
            for i in range(5):
                cache.set(f"k{i}", i, ttl=3600)
            assert len(cache._entries) <= 2

    def test_lru_entry_evicted_first_at_capacity(self) -> None:
        cache = IdempotencyCache(max_size=2)
        with ambient_clock.use(FixedClock(START)):
            cache.set("a", 1, ttl=3600)
            cache.set("b", 2, ttl=3600)
            cache.get("a")
            cache.set("c", 3, ttl=3600)
            assert "b" not in cache._entries
            assert cache.get("a") == 1
            assert cache.get("c") == 3

    def test_expired_entries_evicted_before_lru(self) -> None:
        cache = IdempotencyCache(max_size=2)
        fixed = FixedClock(START)
        with ambient_clock.use(fixed):
            cache.set("a", 1, ttl=10)
            cache.set("b", 2, ttl=3600)
            fixed.advance(11)
            cache.set("c", 3, ttl=3600)
            assert "a" not in cache._entries
            assert cache.get("b") == 2
            assert cache.get("c") == 3

    def test_clear_empties_cache(self) -> None:
        cache = IdempotencyCache()
        with ambient_clock.use(FixedClock(START)):
            cache.set("a", 1, ttl=3600)
            cache.set("b", 2, ttl=3600)
            cache.clear()
            assert cache.get("a") is None
            assert cache.get("b") is None
            assert not cache._entries
