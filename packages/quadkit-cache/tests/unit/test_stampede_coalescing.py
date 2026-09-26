"""Regression tests for StampedeProtectedCache single-flight semantics.

Guards against two defects found while wiring the resilient-rates demo:

1. The envelope was encoded with ``quadkit.serialization.dumps`` (bytes)
   instead of ``json.dumps`` (str), so the memory backend double-encoded it
   and every read missed — coalescing never happened.
2. ``_get_from_cache`` did not unwrap the backend's ``Result`` wrapper, so
   the parsed payload was the Result object itself and every read was
   treated as a miss.
"""

from __future__ import annotations

import asyncio

import pytest

from quadkit.cache.backends.memory.backend import MemoryCacheBackend
from quadkit.cache.service.stampede import StampedeProtectedCache


@pytest.mark.asyncio
async def test_concurrent_calls_coalesce_into_single_compute() -> None:
    backend = MemoryCacheBackend()
    protection = StampedeProtectedCache(cache=backend)
    calls = {"count": 0}

    async def compute() -> dict[str, int]:
        calls["count"] += 1
        await asyncio.sleep(0.02)  # widen the race window
        return {"rate": 1.2345}

    results = await asyncio.gather(
        *(protection.get_or_compute("fx:USD/JPY", compute, ttl=60) for _ in range(10))
    )

    assert calls["count"] == 1
    assert all(r == {"rate": 1.2345} for r in results)


@pytest.mark.asyncio
async def test_second_sequential_call_is_served_from_cache() -> None:
    backend = MemoryCacheBackend()
    protection = StampedeProtectedCache(cache=backend)
    calls = {"count": 0}

    async def compute() -> dict[str, str]:
        calls["count"] += 1
        return {"pair": "EUR/USD"}

    await protection.get_or_compute("fx:EUR/USD", compute, ttl=60)
    await protection.get_or_compute("fx:EUR/USD", compute, ttl=60)

    assert calls["count"] == 1
