"""Unit tests for InMemoryWorkflowStateStore (P6.1).

Tests:
- save_state / load_state round-trip
- load_state returns None for unknown workflow
- list_active returns only PENDING / RUNNING workflows
- delete_state removes the stored workflow
- multiple workflows can be stored independently
- WorkflowResult fields are preserved through serialization
"""

from __future__ import annotations

import pytest

from quadkit.tasks.workflows.core import (
    StepResult,
    WorkflowResult,
    WorkflowStatus,
)
from quadkit.tasks.workflows.state import (
    InMemoryWorkflowStateStore,
    WorkflowSummary,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_result(
    workflow_id: str = "wf-1",
    status: WorkflowStatus = WorkflowStatus.RUNNING,
    steps: list[StepResult] | None = None,
    error: str | None = None,
    total_duration_ms: float = 0.0,
) -> WorkflowResult:
    return WorkflowResult(
        workflow_id=workflow_id,
        status=status,
        steps=steps or [],
        error=error,
        total_duration_ms=total_duration_ms,
    )


def _make_step(name: str = "step1", success: bool = True) -> StepResult:
    return StepResult(
        step_name=name,
        success=success,
        data={"output": "value"},
        error=None if success else "failed",
        duration_ms=12.5,
    )


# ---------------------------------------------------------------------------
# P6.1 — InMemoryWorkflowStateStore
# ---------------------------------------------------------------------------


class TestSaveAndLoad:
    @pytest.mark.asyncio
    async def test_save_and_load_round_trip(self):
        store = InMemoryWorkflowStateStore()
        result = _make_result(workflow_id="wf-1", status=WorkflowStatus.RUNNING)

        await store.save_state("wf-1", result)
        loaded = await store.load_state("wf-1")

        assert loaded is not None
        assert loaded.workflow_id == "wf-1"
        assert loaded.status == WorkflowStatus.RUNNING

    @pytest.mark.asyncio
    async def test_load_returns_none_for_unknown_id(self):
        store = InMemoryWorkflowStateStore()

        loaded = await store.load_state("nonexistent")

        assert loaded is None

    @pytest.mark.asyncio
    async def test_save_overwrites_existing_state(self):
        store = InMemoryWorkflowStateStore()

        await store.save_state("wf-1", _make_result(status=WorkflowStatus.RUNNING))
        await store.save_state("wf-1", _make_result(status=WorkflowStatus.COMPLETED))

        loaded = await store.load_state("wf-1")
        assert loaded is not None
        assert loaded.status == WorkflowStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_steps_are_preserved(self):
        store = InMemoryWorkflowStateStore()
        step = _make_step("stage-a", success=True)
        result = _make_result(steps=[step])

        await store.save_state("wf-1", result)
        loaded = await store.load_state("wf-1")

        assert loaded is not None
        assert len(loaded.steps) == 1
        assert loaded.steps[0].step_name == "stage-a"
        assert loaded.steps[0].success is True

    @pytest.mark.asyncio
    async def test_error_field_is_preserved(self):
        store = InMemoryWorkflowStateStore()
        result = _make_result(status=WorkflowStatus.FAILED, error="something broke")

        await store.save_state("wf-err", result)
        loaded = await store.load_state("wf-err")

        assert loaded is not None
        assert loaded.error == "something broke"
        assert loaded.status == WorkflowStatus.FAILED

    @pytest.mark.asyncio
    async def test_multiple_workflows_stored_independently(self):
        store = InMemoryWorkflowStateStore()

        await store.save_state("wf-a", _make_result("wf-a", WorkflowStatus.PENDING))
        await store.save_state("wf-b", _make_result("wf-b", WorkflowStatus.COMPLETED))

        a = await store.load_state("wf-a")
        b = await store.load_state("wf-b")

        assert a is not None and a.status == WorkflowStatus.PENDING
        assert b is not None and b.status == WorkflowStatus.COMPLETED


class TestListActive:
    @pytest.mark.asyncio
    async def test_list_active_returns_pending_and_running(self):
        store = InMemoryWorkflowStateStore()

        await store.save_state("wf-pending", _make_result("wf-pending", WorkflowStatus.PENDING))
        await store.save_state("wf-running", _make_result("wf-running", WorkflowStatus.RUNNING))
        await store.save_state("wf-done", _make_result("wf-done", WorkflowStatus.COMPLETED))
        await store.save_state("wf-fail", _make_result("wf-fail", WorkflowStatus.FAILED))

        active = await store.list_active()
        active_ids = {s.workflow_id for s in active}

        assert "wf-pending" in active_ids
        assert "wf-running" in active_ids
        assert "wf-done" not in active_ids
        assert "wf-fail" not in active_ids

    @pytest.mark.asyncio
    async def test_list_active_empty_when_no_workflows(self):
        store = InMemoryWorkflowStateStore()

        active = await store.list_active()

        assert active == []

    @pytest.mark.asyncio
    async def test_list_active_returns_workflow_summaries(self):
        store = InMemoryWorkflowStateStore()
        await store.save_state("wf-run", _make_result("wf-run", WorkflowStatus.RUNNING))

        active = await store.list_active()

        assert len(active) == 1
        summary = active[0]
        assert isinstance(summary, WorkflowSummary)
        assert summary.workflow_id == "wf-run"
        assert summary.status == WorkflowStatus.RUNNING

    @pytest.mark.asyncio
    async def test_list_active_excludes_partially_completed(self):
        """PARTIALLY_COMPLETED is a terminal-ish status; not active."""
        store = InMemoryWorkflowStateStore()
        await store.save_state(
            "wf-partial",
            _make_result("wf-partial", WorkflowStatus.PARTIALLY_COMPLETED),
        )

        active = await store.list_active()

        assert all(s.workflow_id != "wf-partial" for s in active)

    @pytest.mark.asyncio
    async def test_list_active_returns_only_active_after_status_update(self):
        store = InMemoryWorkflowStateStore()

        await store.save_state("wf-1", _make_result("wf-1", WorkflowStatus.RUNNING))
        active_before = await store.list_active()
        assert len(active_before) == 1

        # Transition to completed
        await store.save_state("wf-1", _make_result("wf-1", WorkflowStatus.COMPLETED))
        active_after = await store.list_active()
        assert len(active_after) == 0


class TestDeleteState:
    @pytest.mark.asyncio
    async def test_delete_removes_workflow(self):
        store = InMemoryWorkflowStateStore()
        await store.save_state("wf-1", _make_result())

        await store.delete_state("wf-1")

        loaded = await store.load_state("wf-1")
        assert loaded is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_does_not_raise(self):
        store = InMemoryWorkflowStateStore()

        # Should not raise
        await store.delete_state("does-not-exist")

    @pytest.mark.asyncio
    async def test_delete_removes_only_target_workflow(self):
        store = InMemoryWorkflowStateStore()
        await store.save_state("wf-1", _make_result("wf-1"))
        await store.save_state("wf-2", _make_result("wf-2"))

        await store.delete_state("wf-1")

        assert await store.load_state("wf-1") is None
        assert await store.load_state("wf-2") is not None

    @pytest.mark.asyncio
    async def test_delete_removes_from_list_active(self):
        store = InMemoryWorkflowStateStore()
        await store.save_state("wf-1", _make_result("wf-1", WorkflowStatus.RUNNING))

        await store.delete_state("wf-1")

        active = await store.list_active()
        assert all(s.workflow_id != "wf-1" for s in active)
