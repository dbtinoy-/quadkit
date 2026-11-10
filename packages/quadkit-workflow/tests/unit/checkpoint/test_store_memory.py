"""Unit tests for InMemoryContentCheckpointStore."""
from __future__ import annotations

from datetime import datetime

import pytest

from quadkit.contracts.workflow.content_checkpoint import (
    ContentCheckpointEntry,
    ContentCheckpointKey,
)
from quadkit.workflow.checkpoint.store_memory import InMemoryContentCheckpointStore


@pytest.fixture()
def store() -> InMemoryContentCheckpointStore:
    return InMemoryContentCheckpointStore()


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


class TestInMemoryContentCheckpointStore:
    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_none(
        self, store: InMemoryContentCheckpointStore, sample_key: ContentCheckpointKey
    ):
        result = await store.get(sample_key)
        assert result is None

    @pytest.mark.asyncio
    async def test_set_and_get(
        self,
        store: InMemoryContentCheckpointStore,
        sample_key: ContentCheckpointKey,
        sample_entry: ContentCheckpointEntry,
    ):
        await store.set(sample_key, sample_entry)
        result = await store.get(sample_key)
        assert result is not None
        assert result.output == {"result": "ok"}
        assert result.output_blob_ref is None

    @pytest.mark.asyncio
    async def test_evict_removes_entry(
        self,
        store: InMemoryContentCheckpointStore,
        sample_key: ContentCheckpointKey,
        sample_entry: ContentCheckpointEntry,
    ):
        await store.set(sample_key, sample_entry)
        await store.evict(sample_key)
        result = await store.get(sample_key)
        assert result is None

    @pytest.mark.asyncio
    async def test_list_by_stage(self, store: InMemoryContentCheckpointStore):
        key1 = ContentCheckpointKey("stage-a", "t1", b"\x00" * 32, b"\x01" * 32)
        key2 = ContentCheckpointKey("stage-a", "t1", b"\x02" * 32, b"\x01" * 32)
        key3 = ContentCheckpointKey("stage-b", "t1", b"\x03" * 32, b"\x01" * 32)
        entry = ContentCheckpointEntry("out", None, datetime(2026, 6, 3), "v1", 3)

        await store.set(key1, entry)
        await store.set(key2, entry)
        await store.set(key3, entry)

        result = await store.list_by_stage("stage-a", tenant_id="t1")
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_list_by_stage_filters_tenant(self, store: InMemoryContentCheckpointStore):
        key1 = ContentCheckpointKey("stage-a", "t1", b"\x00" * 32, b"\x01" * 32)
        key2 = ContentCheckpointKey("stage-a", "t2", b"\x02" * 32, b"\x01" * 32)
        entry = ContentCheckpointEntry("out", None, datetime(2026, 6, 3), "v1", 3)

        await store.set(key1, entry)
        await store.set(key2, entry)

        result = await store.list_by_stage("stage-a", tenant_id="t1")
        assert len(result) == 1
        assert result[0].tenant_id == "t1"

    @pytest.mark.asyncio
    async def test_evict_nonexistent_does_not_raise(
        self, store: InMemoryContentCheckpointStore, sample_key: ContentCheckpointKey
    ):
        await store.evict(sample_key)
