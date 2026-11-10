"""Unit tests for the orchestration saga primitives."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from quadkit.result import Err, Ok
from quadkit.workflow.saga import AbstractSaga, SagaError, SagaState, SagaStep


# ---------------------------------------------------------------------------
# Concrete test saga
# ---------------------------------------------------------------------------


class _SimpleSaga(AbstractSaga[None]):
    """Minimal concrete saga for testing."""

    def __init__(self, saga_id: str = "test-saga-1", **kwargs) -> None:
        super().__init__(**kwargs)
        self._saga_id = saga_id

    def get_id(self) -> str:
        return self._saga_id

    def is_completed(self) -> bool:
        return self.state == SagaState.COMPLETED


def _make_step(
    name: str,
    *,
    succeeds: bool = True,
    fail_value: str = "step failed",
) -> tuple[SagaStep, AsyncMock, AsyncMock]:
    action = AsyncMock(return_value=Ok(None) if succeeds else Err(fail_value))
    compensation = AsyncMock()
    step = SagaStep(name=name, action=action, compensation=compensation)
    return step, action, compensation


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_all_steps_succeed():
    saga = _SimpleSaga()
    step1, act1, comp1 = _make_step("step-1")
    step2, act2, comp2 = _make_step("step-2")
    saga.add_step(step1)
    saga.add_step(step2)

    result = await saga.execute()

    assert result.is_ok()
    assert saga.state == SagaState.COMPLETED
    assert saga.is_completed()
    act1.assert_awaited_once()
    act2.assert_awaited_once()
    comp1.assert_not_awaited()
    comp2.assert_not_awaited()


# ---------------------------------------------------------------------------
# Failure + compensation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_first_step_fails_no_compensation_needed():
    saga = _SimpleSaga()
    step1, act1, comp1 = _make_step("step-1", succeeds=False)
    step2, act2, comp2 = _make_step("step-2")
    saga.add_step(step1)
    saga.add_step(step2)

    result = await saga.execute()

    assert result.is_err()
    err = result.unwrap_err()
    assert isinstance(err, SagaError)
    assert err.step_name == "step-1"
    # Step 1 failed before completing, so no compensation for step 1.
    comp1.assert_not_awaited()
    # Step 2 was never started.
    act2.assert_not_awaited()
    comp2.assert_not_awaited()
    assert saga.state == SagaState.FAILED


@pytest.mark.asyncio
async def test_second_step_fails_first_step_compensated():
    saga = _SimpleSaga()
    step1, act1, comp1 = _make_step("step-1", succeeds=True)
    step2, act2, comp2 = _make_step("step-2", succeeds=False)
    step3, act3, comp3 = _make_step("step-3", succeeds=True)
    saga.add_step(step1)
    saga.add_step(step2)
    saga.add_step(step3)

    result = await saga.execute()

    assert result.is_err()
    err = result.unwrap_err()
    assert err.step_name == "step-2"
    # Step 1 completed, so its compensation must run.
    comp1.assert_awaited_once()
    # Step 2 failed — no compensation for it.
    comp2.assert_not_awaited()
    # Step 3 was never started.
    act3.assert_not_awaited()
    comp3.assert_not_awaited()
    assert saga.state == SagaState.FAILED


@pytest.mark.asyncio
async def test_compensation_runs_in_reverse_order():
    """Compensations must execute in reverse registration order."""
    call_order: list[str] = []

    async def action_1() -> Ok:
        return Ok(None)

    async def comp_1() -> None:
        call_order.append("comp-1")

    async def action_2() -> Ok:
        return Ok(None)

    async def comp_2() -> None:
        call_order.append("comp-2")

    async def action_3() -> Err:
        return Err("boom")

    async def comp_3() -> None:
        call_order.append("comp-3")  # should never be called

    saga = _SimpleSaga()
    saga.add_step(SagaStep("step-1", action_1, comp_1))
    saga.add_step(SagaStep("step-2", action_2, comp_2))
    saga.add_step(SagaStep("step-3", action_3, comp_3))

    await saga.execute()

    # comp-3 never ran (step-3 failed before completing).
    # comp-2 and comp-1 ran in reverse order.
    assert call_order == ["comp-2", "comp-1"]


@pytest.mark.asyncio
async def test_compensation_continues_if_one_raises():
    """A failing compensation must not prevent subsequent compensations."""
    comp1_ran = False

    async def ok_action():
        return Ok(None)

    async def raising_comp():
        raise RuntimeError("compensation exploded")

    async def ok_comp():
        nonlocal comp1_ran
        comp1_ran = True

    async def fail_action():
        return Err("fail")

    saga = _SimpleSaga()
    saga.add_step(SagaStep("step-1", ok_action, ok_comp))
    saga.add_step(SagaStep("step-2", ok_action, raising_comp))
    saga.add_step(SagaStep("step-3", fail_action, ok_comp))

    result = await saga.execute()

    assert result.is_err()
    # step-1 compensation (ok_comp) must still have run even though
    # step-2's compensation raised.
    assert comp1_ran


# ---------------------------------------------------------------------------
# Manual compensate()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_manual_compensate_runs_completed_steps():
    saga = _SimpleSaga()
    step1, act1, comp1 = _make_step("step-1", succeeds=True)
    saga.add_step(step1)

    # Simulate partial execution by running execute then manually compensating.
    await saga.execute()  # step-1 succeeds → COMPLETED

    # Reset state to RUNNING to allow manual compensate.
    saga.state = SagaState.RUNNING

    await saga.compensate()

    comp1.assert_awaited_once()
    assert saga.state == SagaState.FAILED


# ---------------------------------------------------------------------------
# SagaStore integration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_persists_state_via_store():
    store = AsyncMock()
    store.save = AsyncMock()

    saga = _SimpleSaga(store=store)
    step1, _, _ = _make_step("step-1", succeeds=True)
    saga.add_step(step1)

    await saga.execute()

    # save() must have been called at least for RUNNING and COMPLETED
    assert store.save.await_count >= 2
    calls = [call.args for call in store.save.await_args_list]
    states = [c[1] for c in calls]
    assert SagaState.RUNNING in states
    assert SagaState.COMPLETED in states


@pytest.mark.asyncio
async def test_execute_persists_failed_state_via_store():
    store = AsyncMock()
    store.save = AsyncMock()

    saga = _SimpleSaga(store=store)
    step1, _, _ = _make_step("step-1", succeeds=False)
    saga.add_step(step1)

    await saga.execute()

    states = [call.args[1] for call in store.save.await_args_list]
    assert SagaState.FAILED in states


@pytest.mark.asyncio
async def test_store_error_does_not_abort_saga():
    """A persistence failure must not stop saga execution."""
    store = AsyncMock()
    store.save = AsyncMock(side_effect=OSError("disk full"))

    saga = _SimpleSaga(store=store)
    step1, _, _ = _make_step("step-1", succeeds=True)
    saga.add_step(step1)

    # Should still complete despite store failures.
    result = await saga.execute()
    assert result.is_ok()
    assert saga.state == SagaState.COMPLETED
