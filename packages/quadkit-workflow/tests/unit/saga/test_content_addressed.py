"""Unit tests for ContentAddressedStage and ContentAddressedSaga."""
from __future__ import annotations

from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest

from quadkit.contracts.workflow.content_checkpoint import (
    ContentCheckpointEntry,
    ContentCheckpointKey,
    ContentCheckpointStoreProtocol,
)
from quadkit.result import Ok
from quadkit.workflow.saga import SagaState
from quadkit.workflow.saga.content_addressed import (
    ContentAddressedSaga,
    ContentAddressedStage,
)


@pytest.fixture()
def checkpoint_store() -> AsyncMock:
    store = AsyncMock(spec=ContentCheckpointStoreProtocol)
    store.get = AsyncMock(return_value=None)
    store.set = AsyncMock()
    return store


@pytest.fixture()
def simple_saga(checkpoint_store: AsyncMock) -> ContentAddressedSaga:
    return ContentAddressedSaga(
        saga_id="test-saga",
        checkpoint_store=checkpoint_store,
    )


class TestContentAddressedStage:
    def test_construct_minimal(self):
        async def handler(inputs: dict[str, Any]) -> str:
            return "done"

        stage = ContentAddressedStage(
            stage_id="embed",
            handler=handler,
            handler_version="v1",
        )
        assert stage.stage_id == "embed"
        assert stage.handler_version == "v1"
        assert stage.config_affecting_output == {}
        assert stage.compensation is None

    def test_construct_with_config(self):
        async def handler(inputs: dict[str, Any]) -> str:
            return "done"

        stage = ContentAddressedStage(
            stage_id="embed",
            handler=handler,
            handler_version="v1",
            config_affecting_output={"model": "gpt-4"},
            compensation=handler,
        )
        assert stage.config_affecting_output == {"model": "gpt-4"}
        assert stage.compensation is not None


class TestContentAddressedSagaCacheHit:
    @pytest.mark.asyncio
    async def test_returns_cached_output_when_key_exists(
        self, simple_saga: ContentAddressedSaga
    ):
        handler = AsyncMock(return_value="fresh output")
        stage = ContentAddressedStage("gen", handler, "v1")
        simple_saga.add_stage(stage)

        cached_entry = ContentCheckpointEntry(
            output="cached output",
            output_blob_ref=None,
            completed_at=datetime(2026, 6, 3),
            stage_handler_version="v1",
            output_size_bytes=13,
        )
        simple_saga._checkpoint_store.get = AsyncMock(return_value=cached_entry)

        result = await simple_saga.run_stage(stage, {"text": "hello"})

        assert result == "cached output"
        handler.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_runs_handler_on_cache_miss(self, simple_saga: ContentAddressedSaga):
        handler = AsyncMock(return_value="fresh output")
        stage = ContentAddressedStage("gen", handler, "v1")
        simple_saga.add_stage(stage)

        result = await simple_saga.run_stage(stage, {"text": "hello"})

        assert result == "fresh output"
        handler.assert_awaited_once_with({"text": "hello"})
        simple_saga._checkpoint_store.set.assert_awaited_once()


class TestContentAddressedSagaResume:
    @pytest.mark.asyncio
    async def test_skips_completed_stages_on_resume(
        self, simple_saga: ContentAddressedSaga
    ):
        handler1 = AsyncMock(return_value="step1 output")
        handler2 = AsyncMock(return_value="step2 output")
        stage1 = ContentAddressedStage("step-1", handler1, "v1")
        stage2 = ContentAddressedStage("step-2", handler2, "v1")
        simple_saga.add_stage(stage1)
        simple_saga.add_stage(stage2)

        cached_entry = ContentCheckpointEntry(
            output="cached step1",
            output_blob_ref=None,
            completed_at=datetime(2026, 6, 3),
            stage_handler_version="v1",
            output_size_bytes=12,
        )

        async def mock_get(key: ContentCheckpointKey) -> ContentCheckpointEntry | None:
            if "step-1" in key.stage_id:
                return cached_entry
            return None

        simple_saga._checkpoint_store.get = AsyncMock(side_effect=mock_get)

        result1 = await simple_saga.run_stage(stage1, {})
        result2 = await simple_saga.run_stage(stage2, {})

        assert result1 == "cached step1"
        handler1.assert_not_awaited()
        handler2.assert_awaited_once()


class TestContentAddressedSagaExecute:
    @pytest.mark.asyncio
    async def test_execute_runs_all_stages(self, simple_saga: ContentAddressedSaga):
        handler1 = AsyncMock(return_value="a")
        handler2 = AsyncMock(return_value="b")
        simple_saga.add_stage(ContentAddressedStage("s1", handler1, "v1"))
        simple_saga.add_stage(ContentAddressedStage("s2", handler2, "v1"))

        result = await simple_saga.execute()

        assert result.is_ok()
        assert simple_saga.state == SagaState.COMPLETED
        handler1.assert_awaited_once()
        handler2.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_execute_uses_cached_stages(self, simple_saga: ContentAddressedSaga):
        handler1 = AsyncMock(return_value="a")
        handler2 = AsyncMock(return_value="b")
        simple_saga.add_stage(ContentAddressedStage("s1", handler1, "v1"))
        simple_saga.add_stage(ContentAddressedStage("s2", handler2, "v1"))

        cached = ContentCheckpointEntry(
            output="cached-a",
            output_blob_ref=None,
            completed_at=datetime(2026, 6, 3),
            stage_handler_version="v1",
            output_size_bytes=8,
        )

        async def mock_get(key: ContentCheckpointKey) -> ContentCheckpointEntry | None:
            if key.stage_id == "s1":
                return cached
            return None

        simple_saga._checkpoint_store.get = AsyncMock(side_effect=mock_get)

        result = await simple_saga.execute()

        assert result.is_ok()
        handler1.assert_not_awaited()
        handler2.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_execute_compensates_on_failure(
        self, simple_saga: ContentAddressedSaga
    ):
        events: list[str] = []

        async def ok_handler(inputs: dict[str, Any]) -> str:
            events.append("ok")
            return "ok"

        async def fail_handler(inputs: dict[str, Any]) -> str:
            events.append("fail")
            raise RuntimeError("simulated failure")

        async def comp_handler(inputs: Any) -> None:
            events.append("comp")

        simple_saga.add_stage(
            ContentAddressedStage("s1", ok_handler, "v1", compensation=comp_handler)
        )
        simple_saga.add_stage(ContentAddressedStage("s2", fail_handler, "v1"))

        result = await simple_saga.execute()

        assert result.is_err()
        assert simple_saga.state == SagaState.FAILED
        assert "ok" in events
        assert "fail" in events
        assert "comp" in events


class TestContentAddressedSagaIdentity:
    def test_get_id(self, simple_saga: ContentAddressedSaga):
        assert simple_saga.get_id() == "test-saga"

    def test_is_completed_initial(self, simple_saga: ContentAddressedSaga):
        assert not simple_saga.is_completed()


class TestSagaFailureBoundaryRound15:
    """Round 15: the saga failure boundary must compensate for ANY stage
    error, log (not swallow) compensation failures, and keep persist
    failures from masking outcomes."""

    @pytest.mark.asyncio
    async def test_key_error_stage_triggers_compensation(
        self, simple_saga: ContentAddressedSaga
    ):
        """A KeyError (outside the old RuntimeError/ValueError/OSError tuple)
        must still compensate and return Err — previously it escaped raw
        with no compensation."""
        events: list[str] = []

        async def ok_handler(inputs: dict[str, Any]) -> str:
            events.append("ok")
            return "ok"

        async def key_error_handler(inputs: dict[str, Any]) -> str:
            raise KeyError("missing")

        async def comp_handler(inputs: Any) -> None:
            events.append("comp")

        simple_saga.add_stage(
            ContentAddressedStage("s1", ok_handler, "v1", compensation=comp_handler)
        )
        simple_saga.add_stage(ContentAddressedStage("s2", key_error_handler, "v1"))

        result = await simple_saga.execute()

        assert result.is_err()
        assert simple_saga.state == SagaState.FAILED
        assert events == ["ok", "comp"]

    @pytest.mark.asyncio
    async def test_failing_compensation_does_not_stop_others(
        self, simple_saga: ContentAddressedSaga
    ):
        """A compensation that raises is logged, and later compensations
        (earlier stages) still run."""
        events: list[str] = []

        async def ok1(inputs: dict[str, Any]) -> str:
            return "1"

        async def ok2(inputs: dict[str, Any]) -> str:
            return "2"

        async def fail_handler(inputs: dict[str, Any]) -> str:
            raise IndexError("boom")

        async def comp1(inputs: Any) -> None:
            events.append("comp1")

        async def comp2_raising(inputs: Any) -> None:
            events.append("comp2-raised")
            raise TypeError("compensation broke")

        simple_saga.add_stage(
            ContentAddressedStage("s1", ok1, "v1", compensation=comp1)
        )
        simple_saga.add_stage(
            ContentAddressedStage("s2", ok2, "v1", compensation=comp2_raising)
        )
        simple_saga.add_stage(ContentAddressedStage("s3", fail_handler, "v1"))

        result = await simple_saga.execute()

        assert result.is_err()
        assert simple_saga.state == SagaState.FAILED
        # comp2 raised (logged) but comp1 still ran — reverse order.
        assert events == ["comp2-raised", "comp1"]

    @pytest.mark.asyncio
    async def test_state_store_error_any_type_is_swallowed_and_logged(self) -> None:
        """_persist_state is the single guard point: ANY store error type
        (not just RuntimeError/OSError/ConnectionError/LookupError) is
        logged and never propagates."""
        from quadkit.workflow.saga.content_addressed import ContentAddressedSaga as CAS

        store = AsyncMock()

        async def save_raising(saga_id, state, data):
            raise KeyError("store bug")

        store.save = AsyncMock(side_effect=save_raising)
        saga = CAS(saga_id="t", checkpoint_store=AsyncMock(), store=store)

        # Must not raise, regardless of error type.
        saga.state = SagaState.RUNNING
        await saga._persist_state()
        store.save.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_state_persist_failure_is_advisory(
        self, checkpoint_store: AsyncMock
    ):
        """State-store failures never block execution: the stage checkpoints
        are the durable record, so the saga still completes."""
        from quadkit.workflow.saga.content_addressed import ContentAddressedSaga as CAS

        store = AsyncMock()

        async def save_raising(saga_id, state, data):
            raise OSError("store down")

        store.save = AsyncMock(side_effect=save_raising)
        saga = CAS(saga_id="t", checkpoint_store=checkpoint_store, store=store)
        handler = AsyncMock(return_value="a")
        saga.add_stage(ContentAddressedStage("s1", handler, "v1"))

        result = await saga.execute()

        assert result.is_ok()
        assert saga.state == SagaState.COMPLETED
        handler.assert_awaited_once()
