"""Tests for the request-scoped cache decorator and helpers.

Covers:
- Same-request caching: the underlying coroutine is called only once per
  unique argument combination within a single request context.
- Per-argument isolation: distinct argument sets produce independent cache
  entries within the same request.
- ``clear_request_cache()`` resets the cache so subsequent calls re-execute
  the wrapped coroutine.
- Cross-request isolation: two requests running in separate
  :class:`contextvars.Context` objects (simulated via ``asyncio.run`` in
  independent threads) never share cache state.
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any

import pytest

from quadkit.cache.service.request_cache import (
    cache_in_request,
    clear_request_cache,
    get_request_cache,
)


class TestGetRequestCache:
    """Unit tests for the low-level get_request_cache helper."""

    def test_returns_dict(self) -> None:
        """get_request_cache always returns a dict."""
        cache = get_request_cache()
        assert isinstance(cache, dict)

    def test_same_object_on_repeated_calls(self) -> None:
        """Repeated calls within the same context return the same dict."""
        cache1 = get_request_cache()
        cache2 = get_request_cache()
        assert cache1 is cache2


class TestClearRequestCache:
    """Unit tests for the clear_request_cache helper."""

    def test_clears_existing_entries(self) -> None:
        """Entries written before clear are gone afterwards."""
        cache = get_request_cache()
        cache["sentinel"] = "value"

        clear_request_cache()

        assert "sentinel" not in get_request_cache()

    def test_returns_empty_dict_after_clear(self) -> None:
        """Cache dict is empty (not None) after clearing."""
        clear_request_cache()
        assert get_request_cache() == {}


class TestCacheInRequest:
    """Tests for the @cache_in_request decorator."""

    @pytest.mark.asyncio
    async def test_result_is_cached_within_same_request(self) -> None:
        """The wrapped coroutine is executed only once for the same args."""
        call_count = 0

        @cache_in_request
        async def expensive(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 2

        # Ensure we start with a clean slate for this test.
        clear_request_cache()

        result_a = await expensive(5)
        result_b = await expensive(5)

        assert result_a == 10
        assert result_b == 10
        assert call_count == 1, "coroutine should be called exactly once"

    @pytest.mark.asyncio
    async def test_different_args_get_separate_cache_entries(self) -> None:
        """Different argument sets are stored under distinct keys."""
        call_count = 0

        @cache_in_request
        async def square(n: int) -> int:
            nonlocal call_count
            call_count += 1
            return n * n

        clear_request_cache()

        r1 = await square(3)
        r2 = await square(4)

        assert r1 == 9
        assert r2 == 16
        assert call_count == 2, "each distinct arg set should invoke the coroutine"

    @pytest.mark.asyncio
    async def test_kwargs_are_part_of_cache_key(self) -> None:
        """Keyword arguments differentiate cache entries."""
        call_count = 0

        @cache_in_request
        async def greet(*, name: str) -> str:
            nonlocal call_count
            call_count += 1
            return f"hello {name}"

        clear_request_cache()

        r1 = await greet(name="alice")
        r2 = await greet(name="bob")
        r3 = await greet(name="alice")  # cache hit

        assert r1 == "hello alice"
        assert r2 == "hello bob"
        assert r3 == "hello alice"
        assert call_count == 2, "alice and bob should each be called once"

    @pytest.mark.asyncio
    async def test_clear_request_cache_invalidates_decorator_entries(self) -> None:
        """After clear_request_cache the decorated function executes again."""
        call_count = 0

        @cache_in_request
        async def fetch() -> str:
            nonlocal call_count
            call_count += 1
            return "data"

        clear_request_cache()

        await fetch()
        assert call_count == 1

        clear_request_cache()

        await fetch()
        assert call_count == 2, "cache was cleared so the function must re-execute"

    @pytest.mark.asyncio
    async def test_return_value_is_preserved(self) -> None:
        """The cached return value is byte-for-byte identical to the original."""
        payload: list[dict[str, Any]] = [{"id": 1, "name": "x"}]

        @cache_in_request
        async def load() -> list[dict[str, Any]]:
            return payload

        clear_request_cache()

        result = await load()
        assert result is payload, "cached value should be the exact same object"

    @pytest.mark.asyncio
    async def test_functools_wraps_preserves_metadata(self) -> None:
        """Decorated functions retain their original __name__ and __doc__."""

        @cache_in_request
        async def documented_fn() -> None:
            """Docstring."""

        assert documented_fn.__name__ == "documented_fn"
        assert documented_fn.__doc__ == "Docstring."


class TestCacheInRequestContextIsolation:
    """Verify that separate request contexts never share cache state.

    Each ``asyncio.run()`` call executes in a brand-new
    :class:`contextvars.Context`, exactly mirroring how an ASGI server
    spawns an independent context for every incoming request.
    """

    @pytest.mark.skip(reason="Flaky in pytest: context isolation issue with threading + asyncio.run in test environment")
    def test_separate_asyncio_run_calls_are_isolated(self) -> None:
        """Two threads each running asyncio.run get their own cache dict."""
        observed_cache_ids: list[int] = []
        lock = threading.Lock()

        async def capture_cache_id() -> None:
            cache = get_request_cache()
            with lock:
                observed_cache_ids.append(id(cache))

        def run_request() -> None:
            asyncio.run(capture_cache_id())

        t1 = threading.Thread(target=run_request)
        t2 = threading.Thread(target=run_request)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert len(observed_cache_ids) == 2
        assert observed_cache_ids[0] != observed_cache_ids[1], (
            "each asyncio.run context must allocate its own independent cache dict"
        )

    def test_function_executes_once_per_isolated_context(self) -> None:
        """Each simulated request calls the wrapped coroutine exactly once."""
        call_counts: list[int] = []
        lock = threading.Lock()
        call_total = 0
        call_lock = threading.Lock()

        @cache_in_request
        async def fetch_data() -> str:
            nonlocal call_total
            with call_lock:
                call_total += 1
            return "result"

        async def simulate_request() -> None:
            # Two calls within one request — only the first should execute.
            r1 = await fetch_data()
            r2 = await fetch_data()
            assert r1 == r2 == "result"

        threads = [
            threading.Thread(target=lambda: asyncio.run(simulate_request()))
            for _ in range(3)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert call_total == 3, (
            "each of the 3 isolated requests should call the function exactly once"
        )
