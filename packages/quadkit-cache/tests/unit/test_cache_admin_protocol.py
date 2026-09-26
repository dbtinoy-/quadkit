"""Framework cache admin operations adoption tests."""

from __future__ import annotations

import pytest

from quadkit.cache.backends.memory.backend import MemoryCacheBackend
from quadkit.contracts.infra.cache import CacheAdminProtocol


@pytest.mark.asyncio
async def test_memory_backend_reset_stats_retains_values() -> None:
    """Resetting operational counters must not clear the data plane."""
    backend = MemoryCacheBackend()
    assert isinstance(backend, CacheAdminProtocol)

    await backend.set("operations-key", "still-here")
    assert (await backend.get("operations-key")).unwrap() == "still-here"
    before = backend.get_stats()
    assert before is not None
    assert before["hits"] == 1

    backend.reset_stats()
    after = backend.get_stats()
    assert after is not None
    assert after["hits"] == 0
    assert after["misses"] == 0
    assert (await backend.get("operations-key")).unwrap() == "still-here"
