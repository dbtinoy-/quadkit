"""Tests for saga base orchestration and content-addressed sagas."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from quadkit.contracts.workflow import SagaVersionMismatchError
from quadkit.contracts.workflow.content_checkpoint import (
    ContentCheckpointEntry,
    ContentCheckpointKey,
)
from quadkit.contracts.workflow.protocols import SagaState
from quadkit.contracts.workflow.steps import SagaStep
from quadkit.result import Err, Ok
from quadkit.saga.base import AbstractSaga, SagaError
from quadkit.saga.canonical_json import canonical_json_bytes
from quadkit.saga.content_addressed import (
    ContentAddressedSaga,
    ContentAddressedStage,
)

# ── canonical_json ────────────────────────────────────────────────────────


class TestCanonicalJson:
    def test_deterministic_and_sorted(self) -> None:
        a = canonical_json_bytes({"b": 1, "a": [1, 2]})
        b = canonical_json_bytes({"a": [1, 2], "b": 1})
        assert a == b
        assert b == b'{"a":[1,2],"b":1}'

    def test_unicode_not_escaped(self) -> None:
        out = canonical_json_bytes({"s": "héllo"})
        assert "héllo".encode() in out


# ── AbstractSaga ──────────────────────────────────────────────────────────


def _make_saga_cls():
    class MySaga(AbstractSaga[None]):
        def __init__(self) -> None:
            super().__init__(store=None)
            self.calls: list[str] = []

        def get_id(self) -> str:
            return "saga-1"

        def is_completed(self) -> bool:
            return self.state == SagaState.COMPLETED

    return MySaga


def _step(
    name: str,
    ok: bool = True,
    raises: type[Exception] | None = None,
    comp: Any = None,
    max_retries: int = 1,
    retry_delay: float = 0.0,
    idempotent: bool = True,
) -> SagaStep:
    async def action() -> Any:
        if raises is not None:
            raise raises()
        return Ok("done:" + name)

    return SagaStep(
        name=name,
        action=action,
        compensation=comp,
        max_retries=max_retries,
        retry_delay=retry_delay,
        idempotent=idempotent,
    )


class TestAbstractSaga:
    async def test_execute_all_steps_succeed(self) -> None:
        MySaga = _make_saga_cls()
        saga = MySaga()
        saga.add_step(_step("s1"))
        saga.add_step(_step("s2"))
        result = await saga.execute()
        assert result.is_ok()
        assert saga.state is SagaState.COMPLETED
        assert saga.is_completed()

    async def test_execute_failure_compensates_in_reverse(self) -> None:
        MySaga = _make_saga_cls()
        saga = MySaga()
        compensated: list[str] = []

        async def comp1() -> None:
            compensated.append("s1")

        async def comp2() -> None:
            compensated.append("s2")

        saga.add_step(_step("s1", comp=comp1))
        saga.add_step(_step("s2", comp=comp2))
        saga.add_step(_step("s3", raises=RuntimeError))

        result = await saga.execute()
        assert result.is_err()
        err = result.unwrap_err()
        assert isinstance(err, SagaError)
        assert err.step_name == "s3"
        # s1, s2 completed; s3 failed -> compensation for s2 then s1.
        assert compensated == ["s2", "s1"]
        assert saga.state == SagaState.FAILED
        assert saga.was_compensated("s1")
        assert saga.was_compensated("s2")
        assert not saga.was_compensated("s3")

    async def test_retry_then_succeed(self) -> None:
        MySaga = _make_saga_cls()
        saga = MySaga()
        attempts = 0

        async def flaky() -> Any:
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                return Err(RuntimeError(f"fail-{attempts}"))
            return Ok("ok")

        step = SagaStep(name="flaky", action=flaky, max_retries=3, retry_delay=0.0)
        saga.add_step(step)
        result = await saga.execute()
        assert result.is_ok()
        assert attempts == 3

    async def test_retries_exhausted_fails(self) -> None:
        MySaga = _make_saga_cls()
        saga = MySaga()
        attempts = 0

        async def always_err() -> Any:
            nonlocal attempts
            attempts += 1
            return Err(ValueError("nope"))

        saga.add_step(SagaStep(name="bad", action=always_err, max_retries=2, retry_delay=0.0))
        result = await saga.execute()
        assert result.is_err()
        assert attempts == 2

    async def test_raising_action_counts_as_failure(self) -> None:
        MySaga = _make_saga_cls()
        saga = MySaga()
        saga.add_step(_step("boom", raises=KeyError))
        result = await saga.execute()
        assert result.is_err()
        assert isinstance(result.unwrap_err().cause, KeyError)

    async def test_compensation_failure_does_not_skip_rest(self) -> None:
        MySaga = _make_saga_cls()
        saga = MySaga()
        ran: list[str] = []

        async def bad_comp() -> None:
            ran.append("bad")
            raise RuntimeError("comp failed")

        async def good_comp() -> None:
            ran.append("good")

        saga.add_step(_step("a", comp=good_comp))
        saga.add_step(_step("b", comp=bad_comp))
        saga.add_step(_step("c", raises=ValueError))
        result = await saga.execute()
        assert result.is_err()
        # reversed completed: b (bad, logged) then a (good) — both ran.
        assert ran == ["bad", "good"]
        assert not saga.was_compensated("b")
        assert saga.was_compensated("a")

    async def test_no_compensation_callable_skipped(self) -> None:
        MySaga = _make_saga_cls()
        saga = MySaga()
        saga.add_step(_step("a"))  # no compensation
        saga.add_step(_step("b", raises=RuntimeError))
        result = await saga.execute()
        assert result.is_err()
        assert saga.state == SagaState.FAILED
        assert saga.was_compensated("a") is False

    def test_versioning(self) -> None:
        MySaga = _make_saga_cls()
        saga = MySaga()
        assert saga.get_version() == 1
        assert saga.is_compatible_with(1) is True
        assert saga.is_compatible_with(2) is False

    async def test_mark_compensated_manual(self) -> None:
        MySaga = _make_saga_cls()
        saga = MySaga()
        assert saga.was_compensated("x") is False
        saga.mark_compensated("x")
        assert saga.was_compensated("x") is True

    async def test_manual_compensate(self) -> None:
        MySaga = _make_saga_cls()
        saga = MySaga()
        ran: list[str] = []

        async def comp() -> None:
            ran.append("a")

        saga.add_step(_step("a", comp=comp))
        # No execute — completed_steps empty; compensate still transitions state.
        await saga.compensate()
        assert saga.state == SagaState.FAILED
        assert ran == []


class _FakeSagaStore:
    def __init__(self) -> None:
        self.saved: list[tuple[str, SagaState, dict]] = []
        self.loaded: dict[str, tuple[int, dict] | None] = {}
        self.fail_save = False

    async def save(self, saga_id: str, state: SagaState, data: dict[str, Any]) -> None:
        if self.fail_save:
            raise RuntimeError("store down")
        self.saved.append((saga_id, state, data))

    async def load(self, saga_id: str) -> Any:
        return self.loaded.get(saga_id)


class TestSagaPersistence:
    async def test_persist_state_on_transitions(self) -> None:
        MySaga = _make_saga_cls()
        store = _FakeSagaStore()
        saga = MySaga.__new__(MySaga)
        AbstractSaga.__init__(saga, store=store)
        saga.add_step(_step("s1"))
        await saga.execute()
        states = [s for _, s, _ in store.saved]
        assert states == [SagaState.RUNNING, SagaState.COMPLETED]
        assert store.saved[0][2] == {"version": 1}

    async def test_store_errors_swallowed(self) -> None:
        MySaga = _make_saga_cls()
        store = _FakeSagaStore()
        store.fail_save = True
        saga = MySaga.__new__(MySaga)
        AbstractSaga.__init__(saga, store=store)
        saga.add_step(_step("s1"))
        result = await saga.execute()  # must not raise
        assert result.is_ok()

    async def test_load_state_no_store(self) -> None:
        MySaga = _make_saga_cls()
        saga = MySaga()
        result = await saga._load_state()  # noqa: SLF001
        assert result.is_ok()
        assert result.unwrap() is None

    async def test_load_state_version_mismatch(self) -> None:
        MySaga = _make_saga_cls()
        store = _FakeSagaStore()
        store.loaded["saga-1"] = (2, {"version": 2, "data": "x"})
        saga = MySaga.__new__(MySaga)
        AbstractSaga.__init__(saga, store=store)
        result = await saga._load_state()  # noqa: SLF001
        assert result.is_err()
        assert isinstance(result.unwrap_err(), SagaVersionMismatchError)

    async def test_load_state_legacy_bare_object(self) -> None:
        MySaga = _make_saga_cls()
        store = _FakeSagaStore()
        legacy = type("Legacy", (), {"version": 1})()
        store.loaded["saga-1"] = legacy
        saga = MySaga.__new__(MySaga)
        AbstractSaga.__init__(saga, store=store)
        result = await saga._load_state()  # noqa: SLF001
        assert result.is_ok()
        assert result.unwrap() is legacy


# ── ContentAddressedSaga ──────────────────────────────────────────────────


class _FakeCheckpointStore:
    def __init__(self) -> None:
        self.entries: dict[ContentCheckpointKey, ContentCheckpointEntry] = {}

    async def get(self, key: ContentCheckpointKey) -> ContentCheckpointEntry | None:
        return self.entries.get(key)

    async def set(self, key: ContentCheckpointKey, entry: ContentCheckpointEntry) -> None:
        self.entries[key] = entry


class _FakeBlobStore:
    def __init__(self) -> None:
        self.blobs: dict[str, bytes] = {}
        self.uploads: list[dict[str, Any]] = []

    async def upload(self, path: str, data: bytes, content_type: str) -> None:
        self.blobs[path] = data
        self.uploads.append({"path": path, "data": data, "content_type": content_type})

    async def download(self, path: str) -> bytes:
        return self.blobs[path]


class TestContentAddressedSaga:
    async def test_runs_stages_and_caches(self) -> None:
        checkpoint = _FakeCheckpointStore()
        saga = ContentAddressedSaga("ca-1", checkpoint, tenant_id="t1")
        calls: list[str] = []

        async def handler(inputs: dict[str, Any]) -> Any:
            calls.append("h")
            return {"out": 1}

        saga.add_stage(ContentAddressedStage("stage-1", handler, "v1"))
        result = await saga.execute()
        assert result.is_ok()
        assert calls == ["h"]
        assert len(checkpoint.entries) == 1
        assert saga.is_completed()

    async def test_cached_output_skips_handler(self) -> None:
        checkpoint = _FakeCheckpointStore()
        saga = ContentAddressedSaga("ca-1", checkpoint, tenant_id="t1")
        calls: list[str] = []

        async def handler(inputs: dict[str, Any]) -> Any:
            calls.append("h")
            return {"out": 1}

        stage = ContentAddressedStage("stage-1", handler, "v1")
        saga.add_stage(stage)
        await saga.execute()

        # Second run with identical stage: handler must not be called.
        saga2 = ContentAddressedSaga("ca-1", checkpoint, tenant_id="t1")
        calls.clear()
        saga2.add_stage(ContentAddressedStage("stage-1", handler, "v1"))
        result = await saga2.execute()
        assert result.is_ok()
        assert calls == []

    async def test_different_inputs_use_different_keys(self) -> None:
        k1 = ContentCheckpointKey.compute(
            stage_id="s", tenant_id="t", inputs={"a": 1},
            stage_handler_version="v1", config_affecting_output={},
        )
        k2 = ContentCheckpointKey.compute(
            stage_id="s", tenant_id="t", inputs={"a": 2},
            stage_handler_version="v1", config_affecting_output={},
        )
        k3 = ContentCheckpointKey.compute(
            stage_id="s", tenant_id="t", inputs={"a": 1},
            stage_handler_version="v2", config_affecting_output={},
        )
        assert k1.input_hash != k2.input_hash
        assert k1.config_hash != k3.config_hash

    async def test_large_output_offloaded_to_blob(self) -> None:
        checkpoint = _FakeCheckpointStore()
        blob = _FakeBlobStore()
        saga = ContentAddressedSaga(
            "ca-big", checkpoint, blob_store=blob,
            tenant_id="t9", inline_threshold_bytes=10,
        )

        async def big_handler(inputs: dict[str, Any]) -> Any:
            return {"payload": "x" * 100}

        saga.add_stage(ContentAddressedStage("big", big_handler, "v1"))
        result = await saga.execute()
        assert result.is_ok()
        assert len(blob.uploads) == 1
        upload = blob.uploads[0]
        assert upload["path"].startswith("checkpoints/big/t9/")
        assert upload["path"].endswith(".json")
        assert upload["content_type"] == "application/json"

        entry = next(iter(checkpoint.entries.values()))
        assert entry.output is None
        assert entry.output_blob_ref == upload["path"]
        assert entry.output_size_bytes > 10

    async def test_blob_ref_loaded_on_resume(self) -> None:
        checkpoint = _FakeCheckpointStore()
        blob = _FakeBlobStore()
        saga = ContentAddressedSaga(
            "ca-resume", checkpoint, blob_store=blob,
            tenant_id="t9", inline_threshold_bytes=10,
        )
        async def big_handler(inputs: dict[str, Any]) -> Any:
            return {"payload": "y" * 100}

        saga.add_stage(ContentAddressedStage("big", big_handler, "v1"))
        await saga.execute()

        # Resume: handler replaced (would record a call), blob must be used.
        called = False

        async def new_handler(inputs: dict[str, Any]) -> Any:
            nonlocal called
            called = True
            return {"payload": "different"}

        saga2 = ContentAddressedSaga(
            "ca-resume", checkpoint, blob_store=blob,
            tenant_id="t9", inline_threshold_bytes=10,
        )
        saga2.add_stage(ContentAddressedStage("big", new_handler, "v1"))
        await saga2.execute()
        assert called is False

    async def test_blob_ref_without_blob_store_raises(self) -> None:
        checkpoint = _FakeCheckpointStore()
        key = ContentCheckpointKey.compute(
            stage_id="s", tenant_id=None, inputs={},
            stage_handler_version="v1", config_affecting_output={},
        )
        checkpoint.entries[key] = ContentCheckpointEntry(
            output=None,
            output_blob_ref="checkpoints/s/_global/deadbeef.json",
            completed_at=datetime.now(UTC),
            stage_handler_version="v1",
            output_size_bytes=5,
        )
        saga = ContentAddressedSaga("ca-noblob", checkpoint)

        async def handler(inputs: dict[str, Any]) -> Any:
            return {"ignored": True}

        with pytest.raises(RuntimeError, match="no blob_store"):
            await saga.run_stage(ContentAddressedStage("s", handler, "v1"), {})

    async def test_stage_failure_triggers_compensation_and_err(self) -> None:
        checkpoint = _FakeCheckpointStore()
        saga = ContentAddressedSaga("ca-fail", checkpoint)
        compensated: list[str] = []

        async def ok_handler(inputs: dict[str, Any]) -> Any:
            return 1

        async def bad_handler(inputs: dict[str, Any]) -> Any:
            raise ValueError("stage boom")

        async def comp(inputs: Any) -> None:
            compensated.append("stage-1")

        saga.add_stage(ContentAddressedStage("stage-1", ok_handler, "v1", compensation=comp))
        saga.add_stage(ContentAddressedStage("stage-2", bad_handler, "v1"))
        result = await saga.execute()
        assert result.is_err()
        assert result.unwrap_err().step_name == "stage-2"
        assert compensated == ["stage-1"]
        assert saga.state == SagaState.FAILED

    async def test_global_tenant_blob_path(self) -> None:
        checkpoint = _FakeCheckpointStore()
        blob = _FakeBlobStore()
        saga = ContentAddressedSaga(
            "ca-g", checkpoint, blob_store=blob, inline_threshold_bytes=2,
        )

        async def handler(inputs: dict[str, Any]) -> Any:
            return {"d": "01234"}

        saga.add_stage(ContentAddressedStage("g", handler, "v1"))
        await saga.execute()
        assert "/_global/" in blob.uploads[0]["path"]

    async def test_get_id(self) -> None:
        saga = ContentAddressedSaga("my-id", _FakeCheckpointStore())
        assert saga.get_id() == "my-id"
