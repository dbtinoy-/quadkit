"""Tests for LLM caching core — LLMCache, RedisLLMCache, NoOpLLMCache.

Brings caching/core.py from 28% to full coverage (round 78).
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

import quadkit.ai.llm.caching.core as caching_core
from quadkit.ai.llm.caching.core import LLMCache, NoOpLLMCache, RedisLLMCache
from quadkit.ai.llm.caching.types import CacheEntry, CacheStats
from quadkit.contracts.infra.cache import CacheError
from quadkit.result import Err, Ok

# ---------------------------------------------------------------------------
# LLMCache — basics
# ---------------------------------------------------------------------------


class TestLLMBasics:
    async def test_set_get_roundtrip(self) -> None:
        cache = LLMCache()
        await cache.set("k", {"answer": 42})

        assert await cache.get("k") == {"answer": 42}

    async def test_get_miss_returns_none_and_counts(self) -> None:
        cache = LLMCache()

        assert await cache.get("nope") is None

        stats = cache.get_stats()
        assert stats.misses == 1
        assert stats.hits == 0

    async def test_hit_counts_and_hit_rate(self) -> None:
        cache = LLMCache()
        await cache.set("k", "v")
        await cache.get("k")
        await cache.get("miss")

        stats = cache.get_stats()
        assert stats.hits == 1
        assert stats.misses == 1
        assert stats.hit_rate == pytest.approx(0.5)

    async def test_dict_key_roundtrip_and_key_order_invariance(self) -> None:
        cache = LLMCache()
        await cache.set({"model": "gpt", "prompt": "hi"}, "value")

        assert await cache.get({"prompt": "hi", "model": "gpt"}) == "value"

    async def test_ttl_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        now = 1_000_000.0
        monkeypatch.setattr(caching_core.ambient_clock, "timestamp", lambda: now)

        cache = LLMCache(ttl=3600)
        await cache.set("k", "v", ttl=5)

        entry = next(iter(cache._cache.values()))
        assert entry.expires_at == now + 5

    async def test_expiry(self, monkeypatch: pytest.MonkeyPatch) -> None:
        now = [1_000_000.0]
        monkeypatch.setattr(caching_core.ambient_clock, "timestamp", lambda: now[0])

        cache = LLMCache(ttl=10)
        await cache.set("k", "v")
        assert await cache.get("k") == "v"

        now[0] += 11

        assert await cache.get("k") is None
        stats = cache.get_stats()
        assert stats.evictions == 1
        assert stats.total_entries == 0

    async def test_not_expired_at_exact_boundary(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        now = [1_000_000.0]
        monkeypatch.setattr(caching_core.ambient_clock, "timestamp", lambda: now[0])

        cache = LLMCache(ttl=10)
        await cache.set("k", "v")

        now[0] = 1_000_010.0  # exactly at expires_at — still valid ('>' check)

        assert await cache.get("k") == "v"

    async def test_delete(self) -> None:
        cache = LLMCache()
        await cache.set("k", "v" * 100)
        size_before = cache.get_stats().total_size_bytes

        assert await cache.delete("k") is True
        assert await cache.delete("k") is False
        assert await cache.delete("never-there") is False

        stats = cache.get_stats()
        assert stats.total_entries == 0
        assert stats.total_size_bytes == 0
        assert size_before > 0

    async def test_clear_resets_entries_and_stats(self) -> None:
        cache = LLMCache()
        await cache.set("a", "1")
        await cache.get("a")
        await cache.get("b")

        await cache.clear()

        stats = cache.get_stats()
        assert stats.total_entries == 0
        assert stats.hits == 0
        assert stats.misses == 0
        assert await cache.get("a") is None

    async def test_object_value_roundtrip(self) -> None:
        """Non-plain values are cached by identity; size estimation uses
        the JSON representation (quadkit.serialization is lenient)."""

        class Weird:
            def __str__(self) -> str:
                return "weird-thing"

        cache = LLMCache()
        value = Weird()
        await cache.set("k", value)

        assert await cache.get("k") is value
        assert cache.get_stats().total_size_bytes > 0

    async def test_periodic_expired_eviction_on_get(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        now = [1_000_000.0]
        monkeypatch.setattr(caching_core.ambient_clock, "timestamp", lambda: now[0])

        cache = LLMCache(ttl=3600)
        await cache.set("short-lived", "x", ttl=1)
        for i in range(99):
            await cache.set(f"k{i}", "v")
        assert len(cache._cache) == 100

        now[0] += 2  # "short-lived" expires
        await cache.get("k0")  # len == 100 triggers _evict_expired

        assert cache._hash_key("short-lived") not in cache._cache
        assert len(cache._cache) == 99
        assert cache.get_stats().evictions == 1

    async def test_get_stats_returns_copy(self) -> None:
        cache = LLMCache()
        stats = cache.get_stats()
        stats.hits = 999

        assert cache.get_stats().hits == 0

    async def test_overwrite_does_not_double_count_size(self) -> None:
        cache = LLMCache()
        await cache.set("k", "small")
        size_small = cache.get_stats().total_size_bytes

        await cache.set("k", "a much larger value than before")
        stats = cache.get_stats()

        assert stats.total_entries == 1
        assert stats.total_size_bytes > size_small
        # exactly one entry's worth of bytes — no double counting
        assert stats.total_size_bytes == cache._estimate_size(
            "a much larger value than before"
        )


# ---------------------------------------------------------------------------
# LLMCache — eviction
# ---------------------------------------------------------------------------


class TestEviction:
    async def test_lru_evicts_oldest_created_first(self) -> None:
        cache = LLMCache(ttl=3600, max_size=2)
        await cache.set("a", "1")
        await cache.set("b", "2")
        await cache.set("c", "3")  # evicts "a"

        assert await cache.get("a") is None
        assert await cache.get("b") == "2"
        assert await cache.get("c") == "3"
        assert cache.get_stats().evictions == 1

    async def test_lru_respects_recent_access(self) -> None:
        cache = LLMCache(ttl=3600, max_size=2)
        await cache.set("a", "1")
        await cache.set("b", "2")

        # Touch "a" so "b" becomes the least recently used
        assert await cache.get("a") == "1"
        await cache.set("c", "3")  # must evict "b", not "a"

        assert await cache.get("b") is None
        assert await cache.get("a") == "1"
        assert await cache.get("c") == "3"

    async def test_byte_limit_eviction(self) -> None:
        cache = LLMCache(ttl=3600, max_size=100, max_size_bytes=200)
        await cache.set("small", "tiny")
        await cache.set("big", "x" * 300)  # 302 bytes + 6 > 200 limit

        assert await cache.get("small") is None
        assert await cache.get("big") == "x" * 300

    async def test_max_size_zero_does_not_hang(self) -> None:
        """Regression: the eviction loop used to spin forever on an empty
        cache when max_size=0 (or when a single value exceeded the byte
        limit)."""
        cache = LLMCache(ttl=3600, max_size=0)

        await asyncio.wait_for(cache.set("k", "v"), timeout=2.0)
        await asyncio.wait_for(cache.set("k2", "v2"), timeout=2.0)

        # at most one entry survives in a zero-capacity cache
        assert cache.get_stats().total_entries <= 1

    async def test_oversized_single_value_does_not_hang(self) -> None:
        cache = LLMCache(ttl=3600, max_size=100, max_size_bytes=100)

        await asyncio.wait_for(cache.set("big", "x" * 1000), timeout=2.0)

        assert await cache.get("big") == "x" * 1000


# ---------------------------------------------------------------------------
# LLMCache — get_or_compute
# ---------------------------------------------------------------------------


class TestGetOrCompute:
    async def test_computes_on_miss_and_caches(self) -> None:
        cache = LLMCache()
        calls = 0

        def compute() -> str:
            nonlocal calls
            calls += 1
            return f"result-{calls}"

        first = await cache.get_or_compute("k", compute)
        second = await cache.get_or_compute("k", compute)

        assert first == "result-1"
        assert second == "result-1"
        assert calls == 1

    async def test_supports_async_compute_fn(self) -> None:
        cache = LLMCache()

        async def compute() -> str:
            return "async-result"

        assert await cache.get_or_compute("k", compute) == "async-result"
        assert await cache.get("k") == "async-result"


# ---------------------------------------------------------------------------
# CacheEntry / CacheStats types
# ---------------------------------------------------------------------------


class TestTypes:
    def test_entry_last_access_defaults_to_now(self) -> None:
        entry = CacheEntry(key="k", value="v", expires_at=123.0, size_bytes=1)
        assert entry.last_access_at is not None
        assert entry.hits == 0

    def test_stats_hit_rate_zero_when_empty(self) -> None:
        assert CacheStats().hit_rate == 0.0


# ---------------------------------------------------------------------------
# RedisLLMCache (fake backend)
# ---------------------------------------------------------------------------


class FakeBackend:
    def __init__(self) -> None:
        self.store: dict[str, Any] = {}
        self.ttls: dict[str, int | None] = {}
        self.fail_gets = False
        self.clear_calls = 0

    async def get(self, key: str) -> Any:
        if self.fail_gets:
            return Err(CacheError("backend down"))
        return Ok(self.store.get(key))

    async def set(self, key: str, value: Any, ttl: int | None = None) -> Any:
        self.store[key] = value
        self.ttls[key] = ttl
        return Ok(None)

    async def delete(self, key: str) -> Any:
        if key in self.store:
            del self.store[key]
            return Ok(True)
        return Ok(False)

    async def clear(self) -> Any:
        self.clear_calls += 1
        self.store.clear()
        return Ok(None)


class TestRedisLLMCache:
    async def test_get_hit(self) -> None:
        backend = FakeBackend()
        cache = RedisLLMCache(backend)
        await cache.set("k", "v")

        assert await cache.get("k") == "v"
        assert cache.get_stats().hits == 1

    async def test_get_miss_counts_miss(self) -> None:
        cache = RedisLLMCache(FakeBackend())

        assert await cache.get("nope") is None
        assert cache.get_stats().misses == 1

    async def test_backend_error_counts_miss(self) -> None:
        backend = FakeBackend()
        backend.fail_gets = True
        cache = RedisLLMCache(backend)

        assert await cache.get("k") is None
        assert cache.get_stats().misses == 1
        assert cache.get_stats().hits == 0

    async def test_set_uses_prefixed_hashed_key_and_default_ttl(self) -> None:
        backend = FakeBackend()
        cache = RedisLLMCache(backend, ttl=600)
        await cache.set("k", "v")

        keys = list(backend.store.keys())
        assert len(keys) == 1
        assert keys[0].startswith("llm_cache:")
        assert len(keys[0]) > len("llm_cache:")
        assert backend.ttls[keys[0]] == 600

    async def test_set_ttl_override_is_int(self) -> None:
        backend = FakeBackend()
        cache = RedisLLMCache(backend)
        await cache.set("k", "v", ttl=30.9)

        keys = list(backend.store.keys())
        assert backend.ttls[keys[0]] == 30

    async def test_set_dict_key_matches_str_hash_stability(self) -> None:
        backend = FakeBackend()
        cache = RedisLLMCache(backend)
        await cache.set({"a": 1, "b": 2}, "v")

        assert await cache.get({"b": 2, "a": 1}) == "v"

    async def test_delete(self) -> None:
        backend = FakeBackend()
        cache = RedisLLMCache(backend)
        await cache.set("k", "v")

        assert await cache.delete("k") is True
        assert await cache.delete("k") is False

    async def test_clear_delegates(self) -> None:
        backend = FakeBackend()
        cache = RedisLLMCache(backend)
        await cache.set("k", "v")

        await cache.clear()

        assert backend.clear_calls == 1
        assert backend.store == {}

    async def test_get_or_compute_roundtrip(self) -> None:
        cache = RedisLLMCache(FakeBackend())
        calls = 0

        def compute() -> str:
            nonlocal calls
            calls += 1
            return "computed"

        first = await cache.get_or_compute("k", compute)
        second = await cache.get_or_compute("k", compute)

        assert first == second == "computed"
        assert calls == 1

    async def test_get_or_compute_async_fn(self) -> None:
        cache = RedisLLMCache(FakeBackend())

        async def compute() -> str:
            return "async-computed"

        assert await cache.get_or_compute("k", compute) == "async-computed"
        assert await cache.get("k") == "async-computed"


# ---------------------------------------------------------------------------
# NoOpLLMCache
# ---------------------------------------------------------------------------


class TestNoOpLLMCache:
    async def test_always_misses_and_discards(self) -> None:
        cache = NoOpLLMCache()

        await cache.set("k", "v")
        assert await cache.get("k") is None
        assert await cache.delete("k") is False
        await cache.clear()
        assert cache.get_stats() == {}
