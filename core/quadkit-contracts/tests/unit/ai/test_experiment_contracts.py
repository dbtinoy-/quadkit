"""Tests for experiment tracking contracts: types, status, protocols, exports."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from typing import Any

import pytest

from quadkit.contracts.ai import experiment as exp
from quadkit.contracts.ai.experiment import (
    AblationResult,
    AnalysisReport,
    Checkpoint,
    CheckpointStoreProtocol,
    ErrorRecord,
    ExperimentConfig,
    ExperimentRun,
    ExperimentTrackerProtocol,
    MetricRecord,
    RunStatus,
)


class TestRunStatus:
    def test_values(self) -> None:
        assert RunStatus.RUNNING.value == "running"
        assert RunStatus.COMPLETED.value == "completed"
        assert RunStatus.FAILED.value == "failed"

    def test_str_enum(self) -> None:
        assert RunStatus.RUNNING is RunStatus("running")
        assert str(RunStatus.COMPLETED) == "RunStatus.COMPLETED"

    def test_member_count(self) -> None:
        assert len(RunStatus) == 3


class TestRecords:
    def test_metric_record_frozen(self) -> None:
        m = MetricRecord(step=1, name="score", value=0.5)
        assert m.step == 1
        assert m.name == "score"
        assert m.value == 0.5
        with pytest.raises(FrozenInstanceError):
            m.step = 2  # type: ignore[misc]

    def test_error_record_fields(self) -> None:
        e = ErrorRecord(kind="LLM_RATE_LIMITED", message="slow down", step=3)
        assert e.kind == "LLM_RATE_LIMITED"
        assert e.step == 3


class TestExperimentConfig:
    def test_defaults(self) -> None:
        c = ExperimentConfig(name="exp", seed=7, config={"lr": 0.1})
        assert c.trials == 1
        assert c.metadata == {}

    def test_frozen(self) -> None:
        c = ExperimentConfig(name="exp", seed=7, config={})
        with pytest.raises(FrozenInstanceError):
            c.seed = 8  # type: ignore[misc]

    def test_equality_ignores_config_key_order(self) -> None:
        a = ExperimentConfig(name="e", seed=1, config={"a": 1, "b": 2})
        b = ExperimentConfig(name="e", seed=1, config={"b": 2, "a": 1})
        assert a == b


class TestExperimentRun:
    def _run(self, **kw: Any) -> ExperimentRun:
        base: dict[str, Any] = {
            "run_id": "run-1",
            "experiment": "exp",
            "seed": 42,
            "config": {},
            "config_hash": "abc",
            "status": RunStatus.RUNNING,
            "started_at": "2026-01-01T00:00:00+00:00",
        }
        base.update(kw)
        return ExperimentRun(**base)

    def test_finished_at_default_none(self) -> None:
        assert self._run().finished_at is None

    def test_frozen(self) -> None:
        run = self._run()
        with pytest.raises(FrozenInstanceError):
            run.status = RunStatus.COMPLETED  # type: ignore[misc]


class TestCheckpoint:
    def test_fields(self) -> None:
        cp = Checkpoint(
            run_id="r",
            slug="step10",
            digest="d1",
            payload={"state": 1},
            created_at="2026-01-01T00:00:00+00:00",
        )
        assert cp.slug == "step10"
        assert cp.payload == {"state": 1}


class TestAblationResult:
    def test_fields(self) -> None:
        r = AblationResult(
            run_id="r",
            knob="lr",
            baseline_slug="base",
            ablated_slug="ab",
            deltas={"score": -0.2},
            digest="h",
        )
        assert r.deltas["score"] == -0.2


class TestAnalysisReport:
    def test_no_scores(self) -> None:
        rep = AnalysisReport(
            total_records=2,
            error_count=1,
            error_kinds={"TIMEOUT": 1},
            score_mean=None,
            score_min=None,
            score_max=None,
            top_errors=(ErrorRecord(kind="TIMEOUT", message="t", step=1),),
        )
        assert rep.score_mean is None
        assert len(rep.top_errors) == 1

    def test_with_scores(self) -> None:
        rep = AnalysisReport(
            total_records=3,
            error_count=0,
            error_kinds={},
            score_mean=0.9,
            score_min=0.8,
            score_max=1.0,
            top_errors=(),
        )
        assert rep.top_errors == ()
        assert rep.error_count == 0


class _InMemoryTracker:
    """A concrete tracker implementing the protocol, for conformance checks."""

    def __init__(self) -> None:
        self.runs: dict[str, ExperimentRun] = {}
        self._metrics: dict[str, list[MetricRecord]] = {}
        self._errors: dict[str, list[ErrorRecord]] = {}

    async def start(self, config: ExperimentConfig) -> ExperimentRun:
        run_id = f"{config.name}-{config.seed}"
        if run_id not in self.runs:
            self.runs[run_id] = ExperimentRun(
                run_id=run_id,
                experiment=config.name,
                seed=config.seed,
                config=dict(config.config),
                config_hash="h",
                status=RunStatus.RUNNING,
                started_at="2026-01-01T00:00:00+00:00",
            )
        return self.runs[run_id]

    async def log_metric(self, run_id: str, name: str, value: float, step: int = 0) -> None:
        self._metrics.setdefault(run_id, []).append(MetricRecord(step=step, name=name, value=value))

    async def log_error(self, run_id: str, kind: str, message: str, step: int = 0) -> None:
        self._errors.setdefault(run_id, []).append(ErrorRecord(kind=kind, message=message, step=step))

    async def metrics(self, run_id: str) -> list[MetricRecord]:
        return list(self._metrics.get(run_id, []))

    async def errors(self, run_id: str) -> list[ErrorRecord]:
        return list(self._errors.get(run_id, []))

    async def snapshot(self, run_id: str) -> dict[str, Any]:
        return {"metrics": len(self._metrics.get(run_id, []))}

    async def resume(self, run_id: str) -> ExperimentRun | None:
        return self.runs.get(run_id)

    async def finish(self, run_id: str, status: RunStatus = RunStatus.COMPLETED) -> None:
        self.runs[run_id] = replace(
            self.runs[run_id], status=status, finished_at="2026-01-02T00:00:00+00:00"
        )


class _InMemoryCheckpointStore:
    def __init__(self) -> None:
        self.store: dict[tuple[str, str], Checkpoint] = {}

    async def save(self, run_id: str, slug: str, payload: dict[str, Any]) -> Checkpoint:
        cp = Checkpoint(
            run_id=run_id,
            slug=slug,
            digest=f"hash-{len(payload)}",
            payload=payload,
            created_at="2026-01-01T00:00:00+00:00",
        )
        self.store[(run_id, slug)] = cp
        return cp

    async def load(self, run_id: str, slug: str) -> Checkpoint | None:
        return self.store.get((run_id, slug))

    async def list(self, run_id: str) -> list[Checkpoint]:
        return [cp for (rid, _), cp in self.store.items() if rid == run_id]


class TestProtocolConformance:
    async def test_tracker_protocol_roundtrip(self) -> None:
        tracker: ExperimentTrackerProtocol = _InMemoryTracker()
        cfg = ExperimentConfig(name="exp", seed=1, config={"a": 1})
        run = await tracker.start(cfg)
        assert run.run_id == "exp-1"
        assert run.status is RunStatus.RUNNING

        # resume returns the same run
        again = await tracker.resume(run.run_id)
        assert again is run
        assert await tracker.resume("unknown") is None

        await tracker.log_metric(run.run_id, "score", 0.9, step=1)
        await tracker.log_metric(run.run_id, "latency_ms", 12.0)
        await tracker.log_error(run.run_id, "TIMEOUT", "too slow", step=2)

        metrics = await tracker.metrics(run.run_id)
        assert [m.name for m in metrics] == ["score", "latency_ms"]
        assert metrics[0].value == 0.9
        errors = await tracker.errors(run.run_id)
        assert errors[0].kind == "TIMEOUT"

        snap = await tracker.snapshot(run.run_id)
        assert snap["metrics"] == 2

        await tracker.finish(run.run_id)
        finished = await tracker.resume(run.run_id)
        assert finished is not None
        assert finished.status is RunStatus.COMPLETED
        assert finished.finished_at is not None
        await tracker.finish(run.run_id, RunStatus.FAILED)
        failed = await tracker.resume(run.run_id)
        assert failed is not None
        assert failed.status is RunStatus.FAILED

    async def test_checkpoint_store_roundtrip(self) -> None:
        store: CheckpointStoreProtocol = _InMemoryCheckpointStore()
        cp = await store.save("r", "step10", {"w": 1})
        assert cp.digest == "hash-1"

        loaded = await store.load("r", "step10")
        assert loaded == cp
        assert await store.load("r", "missing") is None
        assert [c.slug for c in await store.list("r")] == ["step10"]
        assert await store.list("other") == []


class TestExports:
    def test_package_exports(self) -> None:
        from quadkit.contracts import ai

        for name in (
            "AblationResult",
            "AnalysisReport",
            "Checkpoint",
            "CheckpointStoreProtocol",
            "ErrorRecord",
            "ExperimentConfig",
            "ExperimentRun",
            "ExperimentTrackerProtocol",
            "MetricRecord",
            "RunStatus",
        ):
            assert hasattr(ai, name), name
            assert getattr(ai, name) is getattr(exp, name), name

    def test_module_all(self) -> None:
        assert "ExperimentTrackerProtocol" in exp.__all__
        assert "RunStatus" in exp.__all__
