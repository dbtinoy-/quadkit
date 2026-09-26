"""Unit tests for CacheBackendResultStore and TaskProvider result-store wiring."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

from quadkit import serialization as json

import pytest

from quadkit.tasks.results import CacheBackendResultStore, InMemoryResultStore
from quadkit.tasks.results.core import ResultStore


class TestCacheBackendResultStore:
    """CacheBackendResultStore delegates to a CacheBackendProtocol."""

    def _make_store(self, *, ttl: int = 3600) -> tuple[CacheBackendResultStore, MagicMock]:
        cache = MagicMock()
        cache.get = AsyncMock(return_value=None)
        cache.set = AsyncMock(return_value=True)
        cache.delete = AsyncMock(return_value=True)
        store = CacheBackendResultStore(cache, ttl=ttl)
        return store, cache

    def _make_result(self, job_id: str = "job-1", status: str = "success") -> MagicMock:
        result = MagicMock()
        result.job_id = job_id
        result.status = status
        result.to_dict.return_value = {"job_id": job_id, "status": status}
        return result

    # -- store / get --

    @pytest.mark.asyncio
    async def test_store_calls_cache_set_with_json(self) -> None:
        store, cache = self._make_store()
        result = self._make_result()

        await store.store("job-1", result)

        assert cache.set.await_count == 2
        call_kwargs = cache.set.call_args_list[0]
        key = call_kwargs[0][0]
        assert "job-1" in key

    @pytest.mark.asyncio
    async def test_store_maintains_completion_index(self) -> None:
        """Storing a result records its id in the completion index."""
        store, cache = self._make_store()
        cache.get = AsyncMock(return_value=None)
        result = self._make_result()

        await store.store("job-1", result)

        index_call = cache.set.call_args_list[1]
        index_key = index_call[0][0]
        assert index_key.endswith("__index__")
        assert "job-1" in index_call[0][1]

    @pytest.mark.asyncio
    async def test_get_completed_returns_successful_newest_first(self) -> None:
        """Returns only successful results, ordered newest first."""
        from quadkit.result import Ok
        from quadkit.tasks.models import JobResult

        store, cache = self._make_store()
        index = '["job-1", "job-2", "job-3"]'
        payloads = {
            "job-1": JobResult(success=True, data="a", id="job-1", name="alpha"),
            "job-2": JobResult(success=False, error="boom", id="job-2", name="beta"),
            "job-3": JobResult(success=True, data="c", id="job-3", name="gamma"),
        }
        cache.get = AsyncMock(
            side_effect=[
                index,
                Ok(json.dumps(payloads["job-3"].to_dict())),
                Ok(json.dumps(payloads["job-2"].to_dict())),
                Ok(json.dumps(payloads["job-1"].to_dict())),
            ]
        )

        completed = await store.get_completed(limit=10)

        assert [r.id for r in completed] == ["job-3", "job-1"]

    @pytest.mark.asyncio
    async def test_get_completed_returns_none_when_no_index(self) -> None:
        """An empty history returns an empty list."""
        store, cache = self._make_store()
        cache.get = AsyncMock(return_value=None)

        completed = await store.get_completed(limit=10)

        assert completed == []

    @pytest.mark.asyncio
    async def test_get_failed_returns_failed_results(self) -> None:
        """Returns only failed results, ordered newest first."""
        from quadkit.result import Ok
        from quadkit.tasks.models import JobResult

        store, cache = self._make_store()
        index = '["job-1", "job-2", "job-3"]'
        payloads = {
            "job-1": JobResult(success=True, data="a", id="job-1", name="alpha"),
            "job-2": JobResult(success=False, error="boom", id="job-2", name="beta"),
            "job-3": JobResult(success=True, data="c", id="job-3", name="gamma"),
        }
        cache.get = AsyncMock(
            side_effect=[
                index,
                Ok(json.dumps(payloads["job-3"].to_dict())),
                Ok(json.dumps(payloads["job-2"].to_dict())),
                Ok(json.dumps(payloads["job-1"].to_dict())),
            ]
        )

        failed = await store.get_failed()

        assert [r.id for r in failed] == ["job-2"]

    @pytest.mark.asyncio
    async def test_get_failed_returns_none_when_no_index(self) -> None:
        """An empty history returns an empty list."""
        store, cache = self._make_store()
        cache.get = AsyncMock(return_value=None)

        failed = await store.get_failed()

        assert failed == []

    @pytest.mark.asyncio
    async def test_get_deserialises_result_wrapper_from_backend(self) -> None:
        """Real backends return values wrapped in Result; they are unwrapped."""
        from quadkit.result import Ok

        store, cache = self._make_store()
        cache.get = AsyncMock(return_value=Ok('{"success": true}'))

        outcome = await store.get("job-1")

        assert outcome is not None
        assert outcome.success is True

    @pytest.mark.asyncio
    async def test_get_returns_none_when_cache_miss(self) -> None:
        store, cache = self._make_store()
        cache.get = AsyncMock(return_value=None)

        result = await store.get("missing")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_deserialises_cached_value(self) -> None:
        from quadkit.tasks.models import JobResult

        store, cache = self._make_store()
        job_result = JobResult.ok(data="done")
        cache.get = AsyncMock(return_value=json.dumps(job_result.to_dict()))

        outcome = await store.get("job-1")

        assert outcome is not None
        assert outcome.success is True
        assert outcome.data == "done"

    # -- delete --

    @pytest.mark.asyncio
    async def test_delete_calls_cache_delete(self) -> None:
        store, cache = self._make_store()
        cache.delete = AsyncMock(return_value=True)

        deleted = await store.delete("job-1")

        assert deleted is True
        cache.delete.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_delete_returns_false_when_not_found(self) -> None:
        store, cache = self._make_store()
        cache.delete = AsyncMock(return_value=False)

        deleted = await store.delete("no-such-job")

        assert deleted is False

    # -- cleanup_expired --

    @pytest.mark.asyncio
    async def test_cleanup_expired_returns_zero(self) -> None:
        store, _ = self._make_store()
        count = await store.cleanup_expired()
        assert count == 0

    # -- wait timeout --

    @pytest.mark.asyncio
    async def test_wait_returns_none_when_timeout_exceeded(self) -> None:
        store, cache = self._make_store()
        cache.get = AsyncMock(return_value=None)

        result = await store.wait("job-1", timeout=0.05, poll_interval=0.01)

        assert result is None

    # -- interface conformance --

    def test_is_subclass_of_result_store(self) -> None:
        store, _ = self._make_store()
        assert isinstance(store, ResultStore)


class TestInMemoryResultStore:
    """InMemoryResultStore basic round-trip (regression guard)."""

    @pytest.mark.asyncio
    async def test_store_and_get_round_trip(self) -> None:
        from quadkit.tasks.models import JobResult

        store = InMemoryResultStore()
        result = JobResult.ok(data=42)

        await store.store("j1", result)
        retrieved = await store.get("j1")

        assert retrieved is not None
        assert retrieved.success is True
        assert retrieved.data == 42

    @pytest.mark.asyncio
    async def test_get_completed_returns_successful_newest_first(self) -> None:
        """Returns only successful results, newest first."""
        from quadkit.tasks.models import JobResult

        store = InMemoryResultStore()
        await store.store("j1", JobResult.ok(data=1))
        await store.store("j2", JobResult.fail("boom"))
        await store.store("j3", JobResult.ok(data=3))

        completed = await store.get_completed(limit=10)

        assert [r.data for r in completed] == [3, 1]

    @pytest.mark.asyncio
    async def test_get_failed_returns_failed_results(self) -> None:
        """Returns only failed results, newest first."""
        from quadkit.tasks.models import JobResult

        store = InMemoryResultStore()
        await store.store("j1", JobResult.ok(data=1))
        await store.store("j2", JobResult.fail("boom"))
        await store.store("j3", JobResult.ok(data=3))

        failed = await store.get_failed()

        assert [r.error for r in failed] == ["boom"]
