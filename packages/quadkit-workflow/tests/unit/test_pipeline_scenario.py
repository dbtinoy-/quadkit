"""Scenario coverage for the in-process pipeline executor.

Exercises ``Pipeline`` (validation, topological ordering, fail-fast vs
continue, skip conditions, error handlers, cleanup, per-step timeout,
resilience wrapping, checkpoint resume) and the step types
(``FunctionStep``, ``ConditionalStep``, ``ParallelStep``) plus the
pipeline decorators.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from quadkit import serialization as json
from quadkit.contracts.exceptions import PipelineExecutionError
from quadkit.primitives.pipeline import PipelineContext, StepStatus
from quadkit.result import Err, Ok, Result
from quadkit.workflow.pipeline import (
    Pipeline,
    conditional,
    parallel,
    pipeline_step,
    step,
)
from quadkit.workflow.pipeline import (
    PipelineContext as PipedContext,
)
from quadkit.workflow.pipeline.steps import (
    ConditionalStep,
    FunctionStep,
    ParallelStep,
    PipelineStep,
)


def _ok_step(name: str, value: Any, deps: list[str] | None = None) -> FunctionStep:
    async def func(context: PipelineContext) -> Result[Any, Exception]:
        return Ok(value)

    return FunctionStep(name, func, deps)


def _fail_step(name: str, exc: Exception | None = None) -> FunctionStep:
    async def func(context: PipelineContext) -> Result[Any, Exception]:
        return Err(exc or ValueError(f"{name} failed"))

    return FunctionStep(name, func)


async def _slow(context: PipelineContext) -> Result[Any, Exception]:
    await asyncio.sleep(0.5)
    return Ok("late")


# --------------------------------------------------------------------------
# Pipeline validation
# --------------------------------------------------------------------------


def test_pipeline_rejects_duplicate_names() -> None:
    with pytest.raises(ValueError, match="Duplicate step names"):
        Pipeline("p", [_ok_step("a", 1), _ok_step("a", 2)])


def test_pipeline_rejects_unknown_dependency() -> None:
    with pytest.raises(ValueError, match="unknown step"):
        Pipeline("p", [_ok_step("a", 1, deps=["ghost"])])


def test_pipeline_rejects_circular_dependency() -> None:
    with pytest.raises(ValueError, match="Circular dependency"):
        Pipeline("p", [_ok_step("a", 1, deps=["b"]), _ok_step("b", 2, deps=["a"])])


def test_pipeline_add_step_validates() -> None:
    pipeline = Pipeline("p", [_ok_step("a", 1)])
    with pytest.raises(ValueError, match="Duplicate step names"):
        pipeline.add_step(_ok_step("a", 2))


def test_pipeline_to_dot() -> None:
    pipeline = Pipeline("order-flow", [_ok_step("b", 2, deps=["a"]), _ok_step("a", 1)])
    dot = pipeline.to_dot()
    assert 'digraph "order-flow"' in dot
    assert '"a";' in dot
    assert '"a" -> "b";' in dot
    assert dot.endswith("}")


# --------------------------------------------------------------------------
# Pipeline execution semantics
# --------------------------------------------------------------------------


async def test_pipeline_runs_in_dependency_order() -> None:
    order: list[str] = []

    async def record(name: str):
        async def func(context: PipelineContext) -> Result[Any, Exception]:
            order.append(name)
            return Ok(name)

        return FunctionStep(name, func, dependencies=order_deps.get(name))

    order_deps = {"a": None, "b": ["a"], "c": ["a"]}
    pipeline = Pipeline("p", [await record("c"), await record("b"), await record("a")])
    result = await pipeline.execute()

    assert result.is_ok()
    context = result.unwrap()
    # a must run first (b and c depend on it); b/c keep their list order
    assert order[0] == "a"
    assert set(order) == {"a", "b", "c"}
    assert context.get_step_result("a") == "a"
    assert context.get_step_result("b") == "b"
    step_results = context.get_metadata("step_results")
    assert [r.step_name for r in step_results] == order
    assert all(r.status == StepStatus.COMPLETED for r in step_results)
    assert context.get_metadata("total_duration") >= 0


async def test_pipeline_fail_fast_stops_after_failure() -> None:
    ran: list[str] = []

    async def tracked(name: str, fail: bool):
        async def func(context: PipelineContext) -> Result[Any, Exception]:
            ran.append(name)
            return Err(ValueError(name)) if fail else Ok(name)

        return FunctionStep(name, func)

    pipeline = Pipeline(
        "p",
        [
            await tracked("a", False),
            await tracked("b", True),
            await tracked("c", False),
        ],
    )
    result = await pipeline.execute(fail_fast=True)

    assert result.is_err()
    assert isinstance(result.unwrap_err(), PipelineExecutionError)
    assert ran == ["a", "b"]  # c never ran


async def test_pipeline_continue_mode_records_failure_and_keeps_going() -> None:
    pipeline = Pipeline("p", [_ok_step("a", 1), _fail_step("b"), _ok_step("c", 3)])
    context = PipelineContext("p")
    result = await pipeline.execute(initial_context=context, fail_fast=False)

    # a failure anywhere still fails the pipeline overall...
    assert result.is_err()
    # ...but later steps did run and the failure is recorded
    assert context.get_step_result("c") == 3
    step_results = context.get_metadata("step_results")
    b_result = next(r for r in step_results if r.step_name == "b")
    assert b_result.status == StepStatus.FAILED
    assert context.has_failed()


async def test_pipeline_error_handler_recovery() -> None:
    async def func(context: PipelineContext) -> Result[Any, Exception]:
        return Err(ValueError("original"))

    async def recover(
        context: PipelineContext, error: Exception
    ) -> Result[Any, Exception]:
        return Ok(f"recovered:{error}")

    failing = FunctionStep("bad", func)
    failing.error_handler = recover
    pipeline = Pipeline("p", [failing, _ok_step("after", 1, deps=["bad"])])
    result = await pipeline.execute()

    assert result.is_ok()
    context = result.unwrap()
    assert context.get_step_result("bad").startswith("recovered:")
    assert context.get_step_result("after") == 1


async def test_pipeline_unhandled_step_error_fails_step() -> None:
    async def func(context: PipelineContext) -> Result[Any, Exception]:
        raise KeyError("missing-config")

    pipeline = Pipeline("p", [FunctionStep("boom", func)])
    result = await pipeline.execute()
    assert result.is_err()
    error = result.unwrap_err()
    assert isinstance(error, PipelineExecutionError)
    assert "missing-config" not in str(error)
    assert "Pipeline step failed" in str(error)


async def test_pipeline_step_timeout_marks_failure() -> None:
    timed_out = FunctionStep("slow", _slow, timeout=0.01)
    pipeline = Pipeline("p", [timed_out])
    result = await pipeline.execute()
    assert result.is_err()


async def test_pipeline_skip_condition() -> None:
    async def skip_if_a(context: PipelineContext) -> Result[bool, Exception]:
        return Ok(context.get_step_result("a") == 1)

    maybe = _ok_step("maybe", 99)
    maybe.skip_condition = skip_if_a
    pipeline = Pipeline("p", [_ok_step("a", 1), maybe])
    result = await pipeline.execute()

    context = result.unwrap()
    assert context.get_step_result("maybe") is None
    step_results = context.get_metadata("step_results")
    maybe_result = next(r for r in step_results if r.step_name == "maybe")
    assert maybe_result.status == StepStatus.SKIPPED


async def test_pipeline_resilience_wrapper() -> None:
    class _FakeResilience:
        def __init__(self) -> None:
            self.calls = 0

        async def execute(self, func: Any, *args: Any, **kwargs: Any) -> Any:
            self.calls += 1
            return await func(*args, **kwargs)

    resilience = _FakeResilience()
    wrapped = _ok_step("w", "resilient")
    wrapped.resilience = resilience
    pipeline = Pipeline("p", [wrapped])
    result = await pipeline.execute()

    assert result.unwrap().get_step_result("w") == "resilient"
    assert resilience.calls == 1


# --------------------------------------------------------------------------
# Pipeline checkpoint resume
# --------------------------------------------------------------------------


class _FakeCacheStore:
    """Dict-backed CacheBackendProtocol fake with error injection."""

    def __init__(self) -> None:
        self.data: dict[str, str] = {}
        self.fail_set = False
        self.fail_get = False
        self.deleted: list[str] = []

    async def get(self, key: str) -> Result[Any, Exception]:
        if self.fail_get:
            raise RuntimeError("store down")
        return Ok(self.data.get(key))

    async def set(self, key: str, value: str) -> Result[None, Exception]:
        if self.fail_set:
            raise RuntimeError("store down")
        self.data[key] = value
        return Ok(None)

    async def delete(self, key: str) -> Result[None, Exception]:
        self.deleted.append(key)
        self.data.pop(key, None)
        return Ok(None)


async def test_pipeline_checkpoint_persist_and_clear() -> None:
    store = _FakeCacheStore()
    pipeline = Pipeline("ck", [_ok_step("a", 1)], checkpoint_store=store)
    result = await pipeline.execute()

    assert result.is_ok()
    key = "pipeline:checkpoint:ck"
    assert key in store.deleted  # cleared after success
    assert key not in store.data


async def test_pipeline_checkpoint_resume_skips_completed() -> None:
    store = _FakeCacheStore()
    store.data["pipeline:checkpoint:ck"] = json.dumps_str({"a": 42})

    ran: list[str] = []

    async def track_a(context: PipelineContext) -> Result[Any, Exception]:
        ran.append("a")
        return Ok(1)

    pipeline = Pipeline(
        "ck",
        [FunctionStep("a", track_a), _ok_step("b", 2, deps=["a"])],
        checkpoint_store=store,
    )
    result = await pipeline.execute()

    context = result.unwrap()
    assert ran == []  # a restored from checkpoint
    assert context.get_step_result("a") == 42
    assert context.get_step_result("b") == 2
    step_results = context.get_metadata("step_results")
    a_result = next(r for r in step_results if r.step_name == "a")
    assert a_result.status == StepStatus.SKIPPED
    assert a_result.skipped_reason == "Resumed from checkpoint"


async def test_pipeline_checkpoint_errors_are_best_effort() -> None:
    # get failure -> warning, pipeline still runs
    store = _FakeCacheStore()
    store.fail_get = True
    pipeline = Pipeline("ck", [_ok_step("a", 1)], checkpoint_store=store)
    assert (await pipeline.execute()).is_ok()

    # set failure -> warning, pipeline still succeeds
    store2 = _FakeCacheStore()
    store2.fail_set = True
    pipeline2 = Pipeline("ck2", [_ok_step("a", 1)], checkpoint_store=store2)
    assert (await pipeline2.execute()).is_ok()


# --------------------------------------------------------------------------
# FunctionStep behaviours
# --------------------------------------------------------------------------


async def test_function_step_sync_and_async_funcs() -> None:
    context = PipelineContext("p")
    sync_step = FunctionStep("s", lambda _ctx: Ok("sync"))
    assert (await sync_step.execute(context)).unwrap() == "sync"
    assert (
        await FunctionStep("a", _slow, timeout=2).execute(context)
    ).unwrap() == "late"


async def test_function_step_exception_becomes_err() -> None:
    async def boom(context: PipelineContext) -> Result[Any, Exception]:
        raise RuntimeError("kapow")

    step = FunctionStep("boom", boom)
    result = await step.execute(PipelineContext("p"))
    assert result.is_err()
    error = result.unwrap_err()
    assert type(error) is Exception
    assert str(error) == "Pipeline step failed (RuntimeError)."


async def test_function_step_timeout() -> None:
    step = FunctionStep("slow", _slow, timeout=0.01)
    result = await step.execute(PipelineContext("p"))
    assert result.is_err()
    assert str(result.unwrap_err()) == "Pipeline step timed out."


async def test_function_step_skip_condition_variants() -> None:
    context = PipelineContext("p")
    # plain bool (sync) normalised to Ok(bool)
    step_bool = FunctionStep("s", lambda _ctx: Ok(0), skip_condition=lambda _ctx: True)
    assert (await step_bool.should_skip(context)).unwrap() is True

    # async Result
    async def cond(ctx: PipelineContext) -> Result[bool, Exception]:
        return Ok(False)

    step_res = FunctionStep("s", _slow, skip_condition=cond)
    assert (await step_res.should_skip(context)).unwrap() is False

    # raising condition -> Err
    def bad(ctx: PipelineContext) -> bool:
        raise ValueError("bad condition")

    step_bad = FunctionStep("s", _slow, skip_condition=bad)
    assert (await step_bad.should_skip(context)).is_err()

    # no condition -> base behaviour Ok(False)
    assert (await _ok_step("n", 1).should_skip(context)).unwrap() is False


async def test_function_step_error_handler_variants() -> None:
    context = PipelineContext("p")
    error = ValueError("orig")

    # sync handler
    step_sync = FunctionStep("s", lambda _ctx: Err(error))
    step_sync.error_handler = lambda _ctx, err: Ok(f"fixed:{err}")
    assert (await step_sync.on_error(context, error)).unwrap() == "fixed:orig"

    # async handler
    async def ahandler(ctx: PipelineContext, err: Exception) -> Result[Any, Exception]:
        return Ok("async-fixed")

    step_async = FunctionStep("s", lambda _ctx: Err(error))
    step_async.error_handler = ahandler
    assert (await step_async.on_error(context, error)).unwrap() == "async-fixed"

    # handler that raises -> Err(handler error)
    step_bad = FunctionStep("s", lambda _ctx: Err(error))
    step_bad.error_handler = lambda _ctx, _err: (_ for _ in ()).throw(
        RuntimeError("handler boom")
    )
    assert (await step_bad.on_error(context, error)).is_err()

    # no handler -> base re-raises
    with pytest.raises(ValueError, match="orig"):
        await _ok_step("n", 1).on_error(context, error)


async def test_function_step_cleanup_variants() -> None:
    context = PipelineContext("p")
    calls: list[str] = []

    def sync_cleanup(ctx: PipelineContext) -> Result[None, Exception]:
        calls.append("sync")
        return Ok(None)

    async def async_cleanup(ctx: PipelineContext) -> Result[None, Exception]:
        calls.append("async")
        return Ok(None)

    async def raising_cleanup(ctx: PipelineContext) -> Result[None, Exception]:
        calls.append("bad")
        raise RuntimeError("cleanup boom")

    s1 = FunctionStep("s1", lambda _ctx: Ok(0), cleanup_func=sync_cleanup)
    s2 = FunctionStep("s2", lambda _ctx: Ok(0), cleanup_func=async_cleanup)
    s3 = FunctionStep("s3", lambda _ctx: Ok(0), cleanup_func=raising_cleanup)

    assert (await s1.cleanup(context)).is_ok()
    assert (await s2.cleanup(context)).is_ok()
    assert (await s3.cleanup(context)).is_err()
    # no cleanup func -> base Ok(None)
    assert (await _ok_step("n", 1).cleanup(context)).is_ok()
    assert calls == ["sync", "async", "bad"]


# --------------------------------------------------------------------------
# ConditionalStep
# --------------------------------------------------------------------------


async def test_conditional_step_branches() -> None:
    context = PipelineContext("p")
    true_step = _ok_step("t", "was-true")
    false_step = _ok_step("f", "was-false")

    async def true_cond(ctx: PipelineContext) -> Result[bool, Exception]:
        return Ok(True)

    async def false_cond(ctx: PipelineContext) -> Result[bool, Exception]:
        return Ok(False)

    async def err_cond(ctx: PipelineContext) -> Result[bool, Exception]:
        return Err(ValueError("cond failed"))

    async def raising_cond(ctx: PipelineContext) -> bool:
        raise RuntimeError("cond boom")

    step_true = ConditionalStep("c1", true_cond, true_step, false_step)
    assert (await step_true.execute(context)).unwrap() == "was-true"

    step_false = ConditionalStep("c2", false_cond, true_step, false_step)
    assert (await step_false.execute(context)).unwrap() == "was-false"

    # false with no false_step -> Ok(None)
    step_no_false = ConditionalStep("c3", false_cond, true_step)
    assert (await step_no_false.execute(context)).unwrap() is None

    # erroring condition propagates Err
    step_err = ConditionalStep("c4", err_cond, true_step)
    assert (await step_err.execute(context)).is_err()

    # raising condition -> Err
    step_raise = ConditionalStep("c5", raising_cond, true_step)
    assert (await step_raise.execute(context)).is_err()

    # sync condition works too
    step_sync = ConditionalStep("c6", lambda _ctx: Ok(True), true_step)
    assert (await step_sync.execute(context)).unwrap() == "was-true"

    # conditional steps never skip
    assert (await step_true.should_skip(context)).unwrap() is False


async def test_conditional_step_timeout() -> None:
    async def slow_cond(ctx: PipelineContext) -> Result[bool, Exception]:
        await asyncio.sleep(0.5)
        return Ok(True)

    step = ConditionalStep("c", slow_cond, _ok_step("t", 1), timeout=0.01)
    result = await step.execute(PipelineContext("p"))
    assert result.is_err()
    assert str(result.unwrap_err()) == "Pipeline condition timed out."


# --------------------------------------------------------------------------
# ParallelStep
# --------------------------------------------------------------------------


class _RaisingStep(PipelineStep):
    """A step whose execute raises instead of returning Err."""

    async def execute(self, context: PipelineContext) -> Result[Any, Exception]:
        msg = f"step {self.name} raised"
        raise RuntimeError(msg)


async def test_parallel_step_success_and_empty() -> None:
    context = PipelineContext("p")
    parallel_step = ParallelStep("par", [_ok_step("a", 1), _ok_step("b", 2)])
    result = await parallel_step.execute(context)
    assert result.unwrap() == [1, 2]

    empty = ParallelStep("empty", [])
    assert (await empty.execute(context)).unwrap() == []


async def test_parallel_step_failure_semantics() -> None:
    context = PipelineContext("p")
    # fail-fast: first failure stops the step
    parallel_step = ParallelStep(
        "par", [_ok_step("a", 1), _fail_step("b"), _ok_step("c", 3)], fail_fast=True
    )
    result = await parallel_step.execute(context)
    assert result.is_err()
    assert isinstance(result.unwrap_err(), PipelineExecutionError)

    # non-fail-fast still reports the error after running everything
    parallel_step2 = ParallelStep(
        "par2", [_ok_step("a", 1), _fail_step("b")], fail_fast=False
    )
    assert (await parallel_step2.execute(context)).is_err()

    # a step that raises (rather than Err) is captured as an error
    parallel_step3 = ParallelStep("par3", [_RaisingStep("x", None)])
    result3 = await parallel_step3.execute(context)
    assert result3.is_err()
    assert isinstance(result3.unwrap_err(), PipelineExecutionError)


async def test_parallel_step_timeout() -> None:
    parallel_step = ParallelStep("par", [FunctionStep("slow", _slow)], timeout=0.01)
    result = await parallel_step.execute(PipelineContext("p"))
    assert result.is_err()
    assert str(result.unwrap_err()) == "Parallel pipeline execution timed out."


# --------------------------------------------------------------------------
# Decorators
# --------------------------------------------------------------------------


def test_pipeline_decorators() -> None:
    async def work(context: PipelineContext) -> Result[Any, Exception]:
        return Ok("decorated")

    s = step("s", work, dependencies=None, timeout=5)
    assert isinstance(s, FunctionStep)
    assert s.name == "s"
    assert s.timeout == 5

    c = conditional("c", lambda _ctx: Ok(True), s, dependencies=None, timeout=2)
    assert isinstance(c, ConditionalStep)
    assert c.timeout == 2

    p = parallel("p", [s], fail_fast=False, timeout=3)
    assert isinstance(p, ParallelStep)
    assert p.fail_fast is False
    assert p.timeout == 3

    @pipeline_step(dependencies=["s"])
    async def other(context: PipelineContext) -> Result[Any, Exception]:
        return Ok("other")

    assert isinstance(other, FunctionStep)
    assert other.name == "other"
    assert other.dependencies == ["s"]

    # package-level re-exports are consistent
    assert PipedContext is PipelineContext
