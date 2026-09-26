"""Focused tests for workflow composition (TaskChain/TaskGroup/TaskChord/BranchStep)."""

from __future__ import annotations

from typing import Any

import pytest

from quadkit.tasks.workflows.core import (
    BranchStep,
    StepResult,
    TaskChain,
    TaskChord,
    TaskGroup,
    TaskStep,
    WorkflowError,
    WorkflowResult,
    WorkflowStatus,
    chain,
)


async def _ok(data: Any) -> Any:
    return f"processed:{data}"


async def _boom(data: Any) -> Any:
    raise ValueError("boom")


async def _takes_forever(data: Any) -> Any:  # pragma: no cover
    import asyncio

    await asyncio.sleep(30)
    return "never"


class FakeStateStore:
    def __init__(self) -> None:
        self.saved: list[WorkflowResult] = []
        self.loaded: WorkflowResult | None = None

    async def load_state(self, workflow_id: str) -> WorkflowResult | None:
        return self.loaded

    async def save_state(self, workflow_id: str, result: WorkflowResult) -> None:
        self.saved.append(result)


class TestWorkflowTypes:
    def test_status_enum(self) -> None:
        assert WorkflowStatus.PENDING.value == "pending"
        assert WorkflowStatus.RUNNING.value == "running"
        assert WorkflowStatus.COMPLETED.value == "completed"
        assert WorkflowStatus.FAILED.value == "failed"
        assert WorkflowStatus.PARTIALLY_COMPLETED.value == "partially_completed"

    def test_workflow_error_code(self) -> None:
        err = WorkflowError("x")
        assert isinstance(err, Exception)
        assert err._code == "QK_ERR_TASK_013"

    def test_step_result_defaults(self) -> None:
        s = StepResult(step_name="a", success=True)
        assert s.data is None
        assert s.error is None
        assert s.duration_ms == 0.0

    def test_workflow_result_defaults(self) -> None:
        w = WorkflowResult(workflow_id="w1", status=WorkflowStatus.PENDING)
        assert w.steps == []
        assert w.final_result is None
        assert w.total_duration_ms == 0.0
        assert w.error is None

    def test_task_step_defaults(self) -> None:
        ts = TaskStep(name="a", handler=_ok)
        assert ts.on_error is None
        assert ts.timeout is None


class TestTaskChain:
    @pytest.mark.asyncio
    async def test_success_chain_threads_data(self) -> None:
        chain_ = TaskChain(
            [TaskStep("one", _ok), TaskStep("two", _ok), TaskStep("three", _ok)]
        )
        result = await chain_.execute("x")
        assert result.is_ok()
        wr = result.unwrap()
        assert wr.status is WorkflowStatus.COMPLETED
        assert wr.final_result == "processed:processed:processed:x"
        assert [s.step_name for s in wr.steps] == ["one", "two", "three"]
        assert all(s.success for s in wr.steps)
        assert wr.workflow_id  # generated

    @pytest.mark.asyncio
    async def test_generated_workflow_id_is_8_chars(self) -> None:
        result = await TaskChain([TaskStep("one", _ok)]).execute()
        assert len(result.unwrap().workflow_id) == 8

    @pytest.mark.asyncio
    async def test_stop_on_error_marks_failed(self) -> None:
        chain_ = TaskChain(
            [TaskStep("ok", _ok), TaskStep("bad", _boom), TaskStep("after", _ok)],
            stop_on_error=True,
        )
        result = await chain_.execute("x")
        wr = result.unwrap()
        assert wr.status is WorkflowStatus.FAILED
        assert wr.error == "Step 'bad' failed: boom"
        assert len(wr.steps) == 2
        assert wr.steps[1].success is False
        assert wr.steps[1].error == "boom"

    @pytest.mark.asyncio
    async def test_continue_on_error(self) -> None:
        chain_ = TaskChain(
            [TaskStep("ok", _ok), TaskStep("bad", _boom), TaskStep("after", _ok)],
            stop_on_error=False,
        )
        result = await chain_.execute("x")
        wr = result.unwrap()
        assert wr.status is WorkflowStatus.COMPLETED
        assert wr.final_result == "processed:processed:x"
        assert [s.success for s in wr.steps] == [True, False, True]

    @pytest.mark.asyncio
    async def test_on_error_handler_recovers(self) -> None:
        async def recover(exc: Exception) -> Any:
            return "recovered"

        chain_ = TaskChain(
            [TaskStep("bad", _boom, on_error=recover), TaskStep("after", _ok)],
            stop_on_error=False,
        )
        wr = (await chain_.execute("x")).unwrap()
        assert wr.final_result == "processed:recovered"
        assert wr.steps[0].success is False

    @pytest.mark.asyncio
    async def test_on_error_handler_failure_isolated(self) -> None:
        async def bad_recover(exc: Exception) -> Any:
            raise RuntimeError("handler broke")

        chain_ = TaskChain(
            [TaskStep("bad", _boom, on_error=bad_recover), TaskStep("after", _ok)],
            stop_on_error=False,
        )
        wr = (await chain_.execute("x")).unwrap()
        assert wr.status is WorkflowStatus.COMPLETED
        assert len(wr.steps) == 2

    @pytest.mark.asyncio
    async def test_timeout_applied(self) -> None:
        chain_ = TaskChain([TaskStep("hung", _takes_forever, timeout=0.05)])
        result = await chain_.execute()
        wr = result.unwrap()
        assert wr.status is WorkflowStatus.FAILED
        assert "timeout" in (wr.error or "").lower() or wr.steps[0].error is not None

    @pytest.mark.asyncio
    async def test_state_store_saves_after_each_step(self) -> None:
        store = FakeStateStore()
        chain_ = TaskChain(
            [TaskStep("one", _ok), TaskStep("two", _ok)],
            state_store=store,
            workflow_id="wf-1",
        )
        wr = (await chain_.execute("x")).unwrap()
        assert wr.workflow_id == "wf-1"
        assert len(store.saved) >= 3  # per-step + final

    @pytest.mark.asyncio
    async def test_resume_skips_completed_steps(self) -> None:
        prior = WorkflowResult(
            workflow_id="wf-1",
            status=WorkflowStatus.RUNNING,
            steps=[
                StepResult(step_name="one", success=True, data="cached:1"),
                StepResult(step_name="two", success=True, data="cached:2"),
            ],
        )
        store = FakeStateStore()
        store.loaded = prior
        chain_ = TaskChain(
            [TaskStep("one", _ok), TaskStep("two", _ok), TaskStep("three", _ok)],
            state_store=store,
            workflow_id="wf-1",
        )
        wr = (await chain_.execute("new")).unwrap()
        assert wr.status is WorkflowStatus.COMPLETED
        assert [s.step_name for s in wr.steps] == ["one", "two", "three"]
        assert wr.final_result == "processed:cached:2"

    @pytest.mark.asyncio
    async def test_resume_only_when_both_store_and_id(self) -> None:
        store = FakeStateStore()
        chain_ = TaskChain([TaskStep("one", _ok)], state_store=store)
        wr = (await chain_.execute("x")).unwrap()
        assert wr.status is WorkflowStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_uphill_error_stops_save_failure(self) -> None:
        class BrokenStore:
            async def load_state(self, workflow_id: str) -> None:
                return None

            async def save_state(self, workflow_id: str, result: WorkflowResult) -> None:
                raise OSError("disk full")

        store = BrokenStore()
        chain_ = TaskChain(
            [TaskStep("one", _ok)],
            state_store=store,
            workflow_id="wf-2",
        )
        result = await chain_.execute("x")
        assert result.is_err()
        assert isinstance(result.unwrap_err(), WorkflowError)

    @pytest.mark.asyncio
    async def test_pipe_operator(self) -> None:
        chain_ = TaskChain([TaskStep("one", _ok)]) | TaskStep("two", _ok)
        assert isinstance(chain_, TaskChain)
        assert [s.name for s in chain_.steps] == ["one", "two"]


class TestTaskGroup:
    @pytest.mark.asyncio
    async def test_all_succeed(self) -> None:
        group = TaskGroup([TaskStep("a", _ok), TaskStep("b", _ok)])
        wr = (await group.execute("x")).unwrap()
        assert wr.status is WorkflowStatus.COMPLETED
        assert wr.final_result == ["processed:x", "processed:x"]
        assert set(s.step_name for s in wr.steps) == {"a", "b"}

    @pytest.mark.asyncio
    async def test_partial_failure(self) -> None:
        group = TaskGroup([TaskStep("a", _ok), TaskStep("b", _boom)])
        wr = (await group.execute("x")).unwrap()
        assert wr.status is WorkflowStatus.PARTIALLY_COMPLETED

    @pytest.mark.asyncio
    async def test_all_fail(self) -> None:
        group = TaskGroup([TaskStep("a", _boom), TaskStep("b", _boom)])
        wr = (await group.execute("x")).unwrap()
        assert wr.status is WorkflowStatus.FAILED
        assert wr.error == "All steps failed"
        assert all(not s.success for s in wr.steps)

    @pytest.mark.asyncio
    async def test_max_concurrency_semaphore(self) -> None:
        group = TaskGroup([TaskStep("a", _ok), TaskStep("b", _ok)], max_concurrency=1)
        wr = (await group.execute("x")).unwrap()
        assert wr.status is WorkflowStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_state_store_saves(self) -> None:
        store = FakeStateStore()
        group = TaskGroup(
            [TaskStep("a", _ok)],
            state_store=store,
            workflow_id="g-1",
        )
        wr = (await group.execute("x")).unwrap()
        assert wr.workflow_id == "g-1"
        assert len(store.saved) == 1

    @pytest.mark.asyncio
    async def test_group_err_from_handler_exception(self) -> None:
        class Catastrophic:
            async def load_state(self, workflow_id: str) -> None:
                return None

            async def save_state(self, workflow_id: str, result: WorkflowResult) -> None:
                raise RuntimeError("infra down")

        group = TaskGroup(
            [TaskStep("a", _ok)],
            state_store=Catastrophic(),
            workflow_id="g-2",
        )
        result = await group.execute("x")
        assert result.is_err()


class TestTaskChord:
    @pytest.mark.asyncio
    async def test_callback_collects_results(self) -> None:
        async def merge(results: Any) -> Any:
            return "|".join(results)

        chord = TaskChord(
            steps=[TaskStep("a", _ok), TaskStep("b", _ok)],
            callback=TaskStep("merge", merge),
        )
        wr = (await chord.execute("x")).unwrap()
        assert wr.status is WorkflowStatus.COMPLETED
        assert wr.final_result == "processed:x|processed:x"
        assert wr.steps[-1].step_name == "merge"

    @pytest.mark.asyncio
    async def test_group_failed_short_circuits_callback(self) -> None:
        chord = TaskChord(
            steps=[TaskStep("a", _boom), TaskStep("b", _boom)],
            callback=TaskStep("merge", _ok),
        )
        wr = (await chord.execute("x")).unwrap()
        assert wr.status is WorkflowStatus.FAILED
        assert wr.steps[-1].step_name != "merge"

    @pytest.mark.asyncio
    async def test_callback_failure_marks_failed(self) -> None:
        chord = TaskChord(
            steps=[TaskStep("a", _ok)],
            callback=TaskStep("merge", _boom),
        )
        wr = (await chord.execute("x")).unwrap()
        assert wr.status is WorkflowStatus.FAILED
        assert wr.error == "Callback 'merge' failed"
        assert wr.steps[-1].success is False


class TestBranchStep:
    @pytest.mark.asyncio
    async def test_true_branch(self) -> None:
        branch = BranchStep(
            condition=lambda data: data["amount"] > 100,
            if_true=TaskStep("approve", _ok),
            if_false=TaskStep("reject", _ok),
        )
        wr = (await branch.execute({"amount": 500})).unwrap()
        assert wr.steps[0].step_name == "approve"
        assert wr.status is WorkflowStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_false_branch(self) -> None:
        branch = BranchStep(
            condition=lambda data: data["amount"] > 100,
            if_true=TaskStep("approve", _ok),
            if_false=TaskStep("reject", _ok),
        )
        wr = (await branch.execute({"amount": 10})).unwrap()
        assert wr.steps[0].step_name == "reject"

    @pytest.mark.asyncio
    async def test_failing_branch_step(self) -> None:
        branch = BranchStep(
            condition=lambda data: True,
            if_true=TaskStep("approve", _boom),
            if_false=TaskStep("reject", _ok),
        )
        wr = (await branch.execute({})).unwrap()
        assert wr.status is WorkflowStatus.FAILED
        assert wr.steps[0].error == "boom"

    @pytest.mark.asyncio
    async def test_condition_raising_returns_err(self) -> None:
        def bad_condition(data: Any) -> bool:
            raise RuntimeError("condition broke")

        branch = BranchStep(
            condition=bad_condition,
            if_true=TaskStep("a", _ok),
            if_false=TaskStep("b", _ok),
        )
        result = await branch.execute({})
        assert result.is_err()
        assert isinstance(result.unwrap_err(), WorkflowError)


class TestFactory:
    @pytest.mark.asyncio
    async def test_chain_factory(self) -> None:
        c = chain(TaskStep("one", _ok), TaskStep("two", _ok))
        assert isinstance(c, TaskChain)
        assert [s.name for s in c.steps] == ["one", "two"]
        wr = (await c.execute("x")).unwrap()
        assert wr.final_result == "processed:processed:x"

    @pytest.mark.asyncio
    async def test_chain_factory_stop_on_error_flag(self) -> None:
        c = chain(TaskStep("one", _ok), stop_on_error=False)
        assert c.stop_on_error is False