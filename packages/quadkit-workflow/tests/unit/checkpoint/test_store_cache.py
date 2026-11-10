"""Unit tests for CacheContentCheckpointStore."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from quadkit.contracts.infra.cache.protocols import CacheBackendProtocol
from quadkit.contracts.workflow.content_checkpoint import (
    ContentCheckpointEntry,
    ContentCheckpointKey,
)
from quadkit.result import Ok
from quadkit.workflow.checkpoint.store_cache import CacheContentCheckpointStore


@pytest.fixture()
def cache_backend() -> AsyncMock:
    backend = AsyncMock(spec=CacheBackendProtocol)
    backend.get = AsyncMock(return_value=Ok(None))
    backend.set = AsyncMock(return_value=Ok(None))
    backend.delete = AsyncMock(return_value=Ok(True))
    return backend


@pytest.fixture()
def store(cache_backend: AsyncMock) -> CacheContentCheckpointStore:
    return CacheContentCheckpointStore(cache_backend)


@pytest.fixture()
def sample_key() -> ContentCheckpointKey:
    return ContentCheckpointKey(
        stage_id="test",
        tenant_id="t1",
        input_hash=b"\x00" * 32,
        config_hash=b"\x01" * 32,
    )


@pytest.fixture()
def sample_entry() -> ContentCheckpointEntry:
    return ContentCheckpointEntry(
        output={"result": "ok"},
        output_blob_ref=None,
        completed_at=datetime(2026, 6, 3),
        stage_handler_version="v1",
        output_size_bytes=16,
    )


class TestCacheContentCheckpointStore:
    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_none(
        self, store: CacheContentCheckpointStore, sample_key: ContentCheckpointKey
    ):
        result = await store.get(sample_key)
        assert result is None

    @pytest.mark.asyncio
    async def test_set_and_get(
        self,
        store: CacheContentCheckpointStore,
        cache_backend: AsyncMock,
        sample_key: ContentCheckpointKey,
        sample_entry: ContentCheckpointEntry,
    ):
        await store.set(sample_key, sample_entry)

        # Mock the get to return the serialized entry
        from quadkit.serialization import dumps
        cache_backend.get = AsyncMock(return_value=Ok(dumps(sample_entry)))

        result = await store.get(sample_key)
        assert result is not None
        assert result.output == {"result": "ok"}
        assert result.stage_handler_version == "v1"

    @pytest.mark.asyncio
    async def test_set_uses_key_str(
        self,
        store: CacheContentCheckpointStore,
        cache_backend: AsyncMock,
        sample_key: ContentCheckpointKey,
        sample_entry: ContentCheckpointEntry,
    ):
        await store.set(sample_key, sample_entry)

        cache_backend.set.assert_awaited_once()
        call_key = cache_backend.set.await_args.args[0]
        assert call_key == sample_key.as_str()

    @pytest.mark.asyncio
    async def test_evict_calls_delete(
        self,
        store: CacheContentCheckpointStore,
        cache_backend: AsyncMock,
        sample_key: ContentCheckpointKey,
    ):
        await store.evict(sample_key)

        cache_backend.delete.assert_awaited_once_with(sample_key.as_str())

    @pytest.mark.asyncio
    async def test_set_with_ttl(
        self,
        cache_backend: AsyncMock,
        sample_key: ContentCheckpointKey,
        sample_entry: ContentCheckpointEntry,
    ):
        store = CacheContentCheckpointStore(cache_backend, default_ttl=3600)
        await store.set(sample_key, sample_entry)

        _, kwargs = cache_backend.set.await_args
        assert kwargs.get("ttl") == 3600

    @pytest.mark.asyncio
    async def test_list_by_stage_returns_empty(
        self, store: CacheContentCheckpointStore
    ):
        """Cache backend does not support listing by stage; returns empty."""
        result = await store.list_by_stage("stage-a")
        assert result == []
