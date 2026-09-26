"""Tests for MemoryCacheBackend.get_stats."""

from __future__ import annotations

from quadkit.cache.backends.memory.backend import MemoryCacheBackend


async def test_memory_backend_tracks_hits_and_evictions() -> None:
    backend = MemoryCacheBackend()
    await backend.set("k", "v")
    assert (await backend.get("k")).unwrap() == "v"
    assert (await backend.get("missing")).unwrap() is None
    await backend.delete("k")
    stats = backend.get_stats()
    assert stats is not None
    assert stats["hits"] == 1
    assert stats["misses"] == 1
    assert stats["evictions"] == 1
    assert stats["entries"] == 0


async def test_memory_backend_get_stats_never_none() -> None:
    backend = MemoryCacheBackend()
    stats = backend.get_stats()
    assert stats is not None
    assert stats["hits"] == 0
    assert stats["misses"] == 0
    assert stats["evictions"] == 0
    assert stats["entries"] == 0


__all__ = [
    "test_memory_backend_get_stats_never_none",
    "test_memory_backend_tracks_hits_and_evictions",
]
