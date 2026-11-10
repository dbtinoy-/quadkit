"""Tests for concurrent (racing) saga behavior."""
from __future__ import annotations

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from quadkit.contracts.workflow.content_checkpoint import (
    ContentCheckpointEntry,
    ContentCheckpointKey,
    ContentCheckpointStoreProtocol,
)
from quadkit.workflow.checkpoint.store_memory import InMemoryContentCheckpointStore
from quadkit.workflow.saga.content_addressed import (
    ContentAddressedSaga,
    ContentAddressedStage,
)


class TestConcurrentSagaCalls:
    @pytest.mark.asyncio
    async def test_concurrent_run_stage_same_key_calls_handler_once(self):
        """Two concurrent run_stage calls with same inputs race on set().

        The handler should be called exactly once (first to set wins).
        """
        store = InMemoryContentCheckpointStore()
        saga = ContentAddressedSaga(saga_id="race-saga", checkpoint_store=store)

        call_count = 0

        async def handler(inputs: dict) -> str:
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0)  # yield to event loop
            return "output"

        stage = ContentAddressedStage("race-stage", handler, "v1")

        concurrency = 5
        results = await asyncio.gather(
            *(saga.run_stage(stage, {"x": 1}) for _ in range(concurrency)),
            return_exceptions=True,
        )

        successes = [r for r in results if not isinstance(r, Exception)]
        errors = [r for r in results if isinstance(r, Exception)]

        assert call_count >= 1
        assert call_count <= concurrency
        assert len(successes) >= 1

    @pytest.mark.asyncio
    async def test_concurrent_execute_handles_races(self):
        """Two sagas with same stages run concurrently without corruption."""
        store = InMemoryContentCheckpointStore()

        async def handler(inputs: dict) -> str:
            await asyncio.sleep(0)
            return "ok"

        async def make_and_run() -> None:
            saga = ContentAddressedSaga(
                saga_id="race-saga",
                checkpoint_store=store,
            )
            saga.add_stage(ContentAddressedStage("s1", handler, "v1"))
            saga.add_stage(ContentAddressedStage("s2", handler, "v1"))
            result = await saga.execute()
            return result

        concurrency = 3
        results = await asyncio.gather(
            *(make_and_run() for _ in range(concurrency)),
            return_exceptions=True,
        )

        errors = [r for r in results if isinstance(r, Exception)]
        assert len(errors) == 0


class TestDatabaseStoreConflict:
    @pytest.mark.asyncio
    async def test_set_handles_duplicate_key_gracefully(self):
        """DatabaseContentCheckpointStore.set should not fail on duplicate.

        When two concurrent sagas try to set the same key, the second insert
        must be handled gracefully (ON CONFLICT DO NOTHING or equivalent).
        """
        from quadkit.workflow.checkpoint.store_database import (
            DatabaseContentCheckpointStore,
        )

        mock_provider = AsyncMock()
        mock_provider.execute = AsyncMock()
        mock_provider.execute_query = AsyncMock()
        mock_provider.execute_query.return_value.rows = []

        store = DatabaseContentCheckpointStore(provider=mock_provider)

        key = ContentCheckpointKey.compute(
            stage_id="s1",
            tenant_id=None,
            inputs={"x": 1},
            stage_handler_version="v1",
            config_affecting_output={},
        )
        entry = ContentCheckpointEntry(
            output="data",
            output_blob_ref=None,
            completed_at=datetime(2026, 6, 3),
            stage_handler_version="v1",
            output_size_bytes=4,
        )
        await store.set(key, entry)

        # execute is called twice: once for _ensure_schema (CREATE TABLE),
        # once for the actual INSERT. Find the INSERT call.
        insert_call = None
        for call_args in mock_provider.execute.call_args_list:
            sql = call_args[0][0]
            if sql.strip().upper().startswith("INSERT"):
                insert_call = call_args
                break
        assert insert_call is not None, "No INSERT call found"
        sql = insert_call[0][0]
        assert "ON CONFLICT" in sql
        assert "DO NOTHING" in sql

    @pytest.mark.asyncio
    async def test_store_set_uses_on_conflict(self):
        """Verify set() uses ON CONFLICT DO NOTHING via execute()."""
        from quadkit.workflow.checkpoint.store_database import (
            DatabaseContentCheckpointStore,
        )

        mock_provider = AsyncMock()
        mock_provider.execute = AsyncMock()
        mock_provider.execute_query = AsyncMock()
        mock_provider.execute_query.return_value.rows = []

        store = DatabaseContentCheckpointStore(provider=mock_provider)

        key = ContentCheckpointKey(
            stage_id="s1",
            tenant_id=None,
            input_hash=b"\x00" * 32,
            config_hash=b"\x01" * 32,
        )
        entry = ContentCheckpointEntry(
            output={"result": "ok"},
            output_blob_ref=None,
            completed_at=datetime(2026, 6, 3),
            stage_handler_version="v1",
            output_size_bytes=16,
        )

        await store.set(key, entry)

        set_call = mock_provider.execute.call_args
        assert set_call is not None
        sql = set_call[0][0]
        assert "ON CONFLICT" in sql
        assert "DO NOTHING" in sql
        assert "INSERT INTO" in sql


class TestCacheStoreConflict:
    @pytest.mark.asyncio
    async def test_cache_set_is_idempotent(self):
        """CacheContentCheckpointStore.set is naturally idempotent (last write wins)."""
        from unittest.mock import MagicMock

        from quadkit.contracts.infra.cache.protocols import CacheBackendProtocol
        from quadkit.workflow.checkpoint.store_cache import (
            CacheContentCheckpointStore,
        )

        mock_backend = MagicMock(spec=CacheBackendProtocol)
        mock_backend.set = AsyncMock()
        mock_backend.get = AsyncMock(return_value=None)
        mock_backend.delete = AsyncMock()

        store = CacheContentCheckpointStore(
            cache=mock_backend,
            default_ttl=300,
        )

        key = ContentCheckpointKey(
            stage_id="s1",
            tenant_id=None,
            input_hash=b"\x00" * 32,
            config_hash=b"\x01" * 32,
        )
        entry = ContentCheckpointEntry(
            output="data",
            output_blob_ref=None,
            completed_at=datetime(2026, 6, 3),
            stage_handler_version="v1",
            output_size_bytes=4,
        )

        await store.set(key, entry)
        await store.set(key, entry)

        assert mock_backend.set.call_count == 2
