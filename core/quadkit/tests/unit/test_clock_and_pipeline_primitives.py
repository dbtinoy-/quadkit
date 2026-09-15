"""Tests for the clock primitive and core pipeline abstractions."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from quadkit.contracts.core.clock import ClockProtocol
from quadkit.primitives import clock
from quadkit.primitives.pipeline import (
    PipelineContext,
    PipelineStep,
    StepExecutionResult,
    StepStatus,
)
from quadkit.result import Err, Ok

# ── Clock ─────────────────────────────────────────────────────────────────


class TestClock:
    def test_now_returns_aware_utc_datetime(self) -> None:
        now = clock.now()
        assert now.tzinfo is UTC

    def test_monotonic_increases(self) -> None:
        a = clock.monotonic()
        b = clock.monotonic()
        assert b >= a

    def test_timestamp_close_to_time(self) -> None:
        import time

        assert abs(clock.timestamp() - time.time()) < 5

    def test_current_returns_active_implementation(self) -> None:
        assert clock.current() is not None
        # SystemClock-backed: .time() exists
        assert callable(clock.current().time)

    def test_install_replaces_active_clock(self) -> None:
        class FakeClock:
            def now(self) -> datetime:
                return datetime(2000, 1, 1, tzinfo=UTC)

            def monotonic(self) -> float:
                return -1.0

            def timestamp(self) -> float:
                return -1.0

            def time(self) -> float:
                return -1.0

        fake = FakeClock()
        try:
            clock.install(fake)
            assert clock.current() is fake
            assert clock.monotonic() == -1.0
            assert clock.timestamp() == -1.0
            assert clock.now() == datetime(2000, 1, 1, tzinfo=UTC)
        finally:
            clock.install(clock._SystemClock())  # noqa: SLF001 — restore default

    def test_use_context_manager_restores(self) -> None:
        class FakeClock:
            def now(self) -> datetime:
                return datetime(1999, 12, 31, tzinfo=UTC)

            def monotonic(self) -> float:
                return 0.0

            def timestamp(self) -> float:
                return 0.0

            def time(self) -> float:
                return 0.0

        before = clock.current()
        with clock.use(FakeClock()):
            assert clock.current() is not before
            assert clock.timestamp() == 0.0
        assert clock.current() is before

    def test_use_restores_on_exception(self) -> None:
        class FakeClock:
            def now(self) -> datetime:
                return datetime(1999, 12, 31, tzinfo=UTC)

            def monotonic(self) -> float:
                return 0.0

            def timestamp(self) -> float:
                return 0.0

            def time(self) -> float:
                return 0.0

        before = clock.current()
        with pytest.raises(RuntimeError):
            with clock.use(FakeClock()):
                raise RuntimeError("boom")
        assert clock.current() is before

    def test_clock_protocol_conformance(self) -> None:
        assert isinstance(clock._SystemClock(), ClockProtocol)  # noqa: SLF001


# ── Pipeline ──────────────────────────────────────────────────────────────


def _ctx() -> PipelineContext:
    return PipelineContext(pipeline_name="test-pipeline")


def _step_result(name: str, status: StepStatus) -> StepExecutionResult:
    return StepExecutionResult(step_name=name, status=status)


class TestStepStatus:
    def test_values_are_strings(self) -> None:
        assert StepStatus.PENDING == "pending"
        assert StepStatus.RUNNING == "running"
        assert StepStatus.COMPLETED == "completed"
        assert StepStatus.FAILED == "failed"
        assert StepStatus.SKIPPED == "skipped"


class TestPipelineContext:
    def test_defaults(self) -> None:
        ctx = _ctx()
        assert ctx.step_results == {}
        assert ctx.metadata == {}
        assert ctx.start_time is None
        assert ctx.end_time is None

    def test_step_result_roundtrip_and_default(self) -> None:
        ctx = _ctx()
        assert ctx.get_step_result("nope") is None
        assert ctx.get_step_result("nope", 42) == 42
        ctx.set_step_result("s1", "value")
        assert ctx.get_step_result("s1") == "value"

    def test_metadata_roundtrip_and_default(self) -> None:
        ctx = _ctx()
        assert ctx.get_metadata("missing") is None
        assert ctx.get_metadata("missing", "dflt") == "dflt"
        ctx.add_metadata("k", [1, 2])
        assert ctx.get_metadata("k") == [1, 2]
        ctx.add_metadata("k", "replaced")
        assert ctx.get_metadata("k") == "replaced"

    def test_duration_without_start_is_zero(self) -> None:
        assert _ctx().duration == 0.0

    async def test_duration_with_start_and_end(self) -> None:
        ctx = _ctx()
        ctx.start_time = 100.0
        ctx.end_time = 105.5
        assert ctx.duration == pytest.approx(5.5)

    async def test_duration_open_ended_uses_event_loop(self) -> None:
        ctx = _ctx()
        ctx.start_time = None
        # start_time set mid-flight: duration from start to loop time
        import asyncio

        loop_now = asyncio.get_event_loop().time()
        ctx.start_time = loop_now - 0.01
        assert ctx.duration >= 0.0

    def test_failed_and_successful_steps(self) -> None:
        ctx = _ctx()
        ok1 = _step_result("a", StepStatus.COMPLETED)
        bad = _step_result("b", StepStatus.FAILED)
        skipped = _step_result("c", StepStatus.SKIPPED)
        ok2 = _step_result("d", StepStatus.COMPLETED)
        ctx.add_metadata(
            "step_results", [ok1, bad, skipped, ok2],
        )
        assert [r.step_name for r in ctx.failed_steps] == ["b"]
        assert [r.step_name for r in ctx.successful_steps] == ["a", "d"]
        assert ctx.has_failed() is True

    def test_no_failures(self) -> None:
        ctx = _ctx()
        ctx.add_metadata("step_results", [_step_result("a", StepStatus.COMPLETED)])
        assert ctx.has_failed() is False
        assert ctx.failed_steps == []

    def test_step_execution_result_defaults(self) -> None:
        r = StepExecutionResult(step_name="x", status=StepStatus.PENDING)
        assert r.result is None
        assert r.error is None
        assert r.duration is None
        assert r.metadata is None
        assert r.skipped_reason is None


class _ConcreteStep(PipelineStep):
    async def execute(self, context: PipelineContext) -> Ok[Any] | Err[Exception]:
        return Ok("executed")


class TestPipelineStep:
    def test_init_defaults(self) -> None:
        step = _ConcreteStep(name="s1")
        assert step.name == "s1"
        assert step.dependencies == []
        assert step.timeout is None
        assert step.resilience is None

    def test_init_explicit(self) -> None:
        sentinel = object()
        step = _ConcreteStep(
            name="s2", dependencies=["s1"], timeout=2.5, resilience=sentinel  # type: ignore[arg-type]
        )
        assert step.dependencies == ["s1"]
        assert step.timeout == 2.5
        assert step.resilience is sentinel

    def test_cannot_instantiate_abstract(self) -> None:
        with pytest.raises(TypeError):
            PipelineStep(name="abstract")  # type: ignore[abstract]

    async def test_default_should_skip_executes(self) -> None:
        result = await _ConcreteStep(name="s").should_skip(_ctx())
        assert result.is_ok()
        assert result.unwrap() is False

    async def test_default_on_error_reraises(self) -> None:
        step = _ConcreteStep(name="s")
        with pytest.raises(ValueError, match="original"):
            await step.on_error(_ctx(), ValueError("original"))

    async def test_default_cleanup_ok_none(self) -> None:
        result = await _ConcreteStep(name="s").cleanup(_ctx())
        assert result.is_ok()
        assert result.unwrap() is None

    async def test_execute_returns_ok(self) -> None:
        result = await _ConcreteStep(name="s").execute(_ctx())
        assert result.unwrap() == "executed"

    async def test_custom_should_skip_true(self) -> None:
        class Skipper(_ConcreteStep):
            async def should_skip(self, context: PipelineContext) -> Ok[bool] | Err[Exception]:
                return Ok(True)

        assert (await Skipper(name="s").should_skip(_ctx())).unwrap() is True

    async def test_custom_should_skip_error(self) -> None:
        class BrokenSkip(_ConcreteStep):
            async def should_skip(self, context: PipelineContext) -> Ok[bool] | Err[Exception]:
                return Err(RuntimeError("condition failed"))

        result = await BrokenSkip(name="s").should_skip(_ctx())
        assert result.is_err()

    async def test_custom_on_error_recovers(self) -> None:
        class Recovering(_ConcreteStep):
            async def on_error(self, context: PipelineContext, error: Exception) -> Any:
                return f"recovered:{error}"

        step = Recovering(name="s")
        assert await step.on_error(_ctx(), ValueError("x")) == "recovered:x"

    async def test_custom_cleanup_recorded(self) -> None:
        class Cleaning(_ConcreteStep):
            def __init__(self) -> None:
                super().__init__(name="cleaner")
                self.cleaned = False

            async def cleanup(self, context: PipelineContext) -> Ok[None] | Err[Exception]:
                self.cleaned = True
                return Ok(None)

            async def execute(  # re-abstract for signature clarity
                self, context: PipelineContext
            ) -> Ok[Any] | Err[Exception]:
                return Ok(None)

        step = Cleaning()
        await step.cleanup(_ctx())
        assert step.cleaned is True
