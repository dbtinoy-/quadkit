"""P2 hook surface import verification for quadkit-cache."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, is_dataclass

import pytest


def test_cache_hooks_root_module_exists() -> None:
    import quadkit.cache
    from quadkit.cache.hooks import (
        CacheConnectedHook,
        CacheDisconnectedHook,
        CacheEntryEvictedHook,
    )

    assert CacheConnectedHook.__name__ == "CacheConnectedHook"
    assert CacheDisconnectedHook.__name__ == "CacheDisconnectedHook"
    assert CacheEntryEvictedHook.__name__ == "CacheEntryEvictedHook"
    assert quadkit.cache.CacheConnectedHook is CacheConnectedHook
    assert quadkit.cache.CacheDisconnectedHook is CacheDisconnectedHook
    assert quadkit.cache.CacheEntryEvictedHook is CacheEntryEvictedHook


def test_cache_hook_payloads_are_frozen_and_keyword_only() -> None:
    from quadkit.cache.hooks import CacheConnectedHook, CacheEntryEvictedHook

    connected = CacheConnectedHook(backend="redis")
    evicted = CacheEntryEvictedHook(key="user:42", backend="redis")

    assert is_dataclass(connected)
    assert is_dataclass(evicted)

    with pytest.raises(TypeError):
        CacheConnectedHook("redis")  # type: ignore[misc]

    with pytest.raises(FrozenInstanceError):
        connected.backend = "memcached"  # type: ignore[misc]
