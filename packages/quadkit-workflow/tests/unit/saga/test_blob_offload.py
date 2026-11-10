"""Unit tests for ContentAddressedSaga blob offload integration."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from quadkit.contracts.workflow.content_checkpoint import (
    ContentCheckpointEntry,
    ContentCheckpointStoreProtocol,
)
from quadkit.workflow.saga.content_addressed import (
    ContentAddressedSaga,
    ContentAddressedStage,
)


@pytest.fixture
def blob_store() -> AsyncMock:
    store = AsyncMock()
    store.upload = AsyncMock(return_value=None)
    store.download = AsyncMock(return_value=b'{"embedding": [0.1, 0.2]}')
    return store


@pytest.fixture
def checkpoint_store() -> AsyncMock:
    store = AsyncMock(spec=ContentCheckpointStoreProtocol)
    store.get = AsyncMock(return_value=None)
    store.set = AsyncMock()
    return store


class TestContentAddressedSagaBlobOffload:
    @pytest.mark.asyncio
    async def test_small_output_stored_inline(
        self, checkpoint_store: AsyncMock
    ):
        """Output under threshold is stored inline (output_blob_ref=None)."""
        saga = ContentAddressedSaga(
            saga_id="test",
            checkpoint_store=checkpoint_store,
            inline_threshold_bytes=1_000_000,
        )
        handler = AsyncMock(return_value="small output")
        stage = ContentAddressedStage("gen", handler, "v1")
        saga.add_stage(stage)

        await saga.run_stage(stage, {"text": "hello"})

        call_args = checkpoint_store.set.await_args
        assert call_args is not None
        entry: ContentCheckpointEntry = call_args.args[1]
        assert entry.output == "small output"
        assert entry.output_blob_ref is None

    @pytest.mark.asyncio
    async def test_large_output_offloaded_to_blob(
        self, checkpoint_store: AsyncMock, blob_store: AsyncMock
    ):
        """Output above threshold is offloaded to blob store."""
        saga = ContentAddressedSaga(
            saga_id="test",
            checkpoint_store=checkpoint_store,
            blob_store=blob_store,
            inline_threshold_bytes=1,  # tiny threshold to force offload
        )
        handler = AsyncMock(return_value="a" * 1000)
        stage = ContentAddressedStage("gen", handler, "v1")
        saga.add_stage(stage)

        await saga.run_stage(stage, {"text": "hello"})

        blob_store.upload.assert_awaited_once()
        call_args = blob_store.upload.await_args
        assert call_args is not None
        path = call_args.kwargs.get("path") or call_args.args[0]
        assert "checkpoints/gen/" in path

        # Checkpoint entry should reference the blob, not store output inline
        checkpoint_set_args = checkpoint_store.set.await_args
        assert checkpoint_set_args is not None
        entry: ContentCheckpointEntry = checkpoint_set_args.args[1]
        assert entry.output is None
        assert entry.output_blob_ref is not None

    @pytest.mark.asyncio
    async def test_no_blob_store_falls_back_to_inline(
        self, checkpoint_store: AsyncMock
    ):
        """When blob_store is None, large output is stored inline anyway."""
        saga = ContentAddressedSaga(
            saga_id="test",
            checkpoint_store=checkpoint_store,
            blob_store=None,
            inline_threshold_bytes=1,
        )
        handler = AsyncMock(return_value="x" * 1000)
        stage = ContentAddressedStage("gen", handler, "v1")
        saga.add_stage(stage)

        await saga.run_stage(stage, {})

        call_args = checkpoint_store.set.await_args
        assert call_args is not None
        entry: ContentCheckpointEntry = call_args.args[1]
        assert entry.output is not None
        assert entry.output_blob_ref is None

    @pytest.mark.asyncio
    async def test_cached_blob_entry_loads_from_blob(
        self, checkpoint_store: AsyncMock, blob_store: AsyncMock
    ):
        """A cached entry with output_blob_ref loads output from blob store."""
        saga = ContentAddressedSaga(
            saga_id="test",
            checkpoint_store=checkpoint_store,
            blob_store=blob_store,
        )
        handler = AsyncMock(return_value="should not run")
        stage = ContentAddressedStage("gen", handler, "v1")
        saga.add_stage(stage)

        cached = ContentCheckpointEntry(
            output=None,
            output_blob_ref="checkpoints/gen/abc123",
            completed_at=datetime(2026, 6, 3),
            stage_handler_version="v1",
            output_size_bytes=100,
        )
        checkpoint_store.get = AsyncMock(return_value=cached)

        result = await saga.run_stage(stage, {})

        blob_store.download.assert_awaited_once_with("checkpoints/gen/abc123")
        handler.assert_not_awaited()
        assert result == {"embedding": [0.1, 0.2]}

    @pytest.mark.asyncio
    async def test_cached_blob_entry_without_blob_store_raises(
        self, checkpoint_store: AsyncMock
    ):
        """Cached blob entry without blob_store configured raises error."""
        saga = ContentAddressedSaga(
            saga_id="test",
            checkpoint_store=checkpoint_store,
            blob_store=None,
        )
        handler = AsyncMock(return_value="should not run")
        stage = ContentAddressedStage("gen", handler, "v1")
        saga.add_stage(stage)

        cached = ContentCheckpointEntry(
            output=None,
            output_blob_ref="checkpoints/gen/abc123",
            completed_at=datetime(2026, 6, 3),
            stage_handler_version="v1",
            output_size_bytes=100,
        )
        checkpoint_store.get = AsyncMock(return_value=cached)

        with pytest.raises(RuntimeError, match="blob_store"):
            await saga.run_stage(stage, {})
