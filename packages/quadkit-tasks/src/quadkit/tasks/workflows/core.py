"""Task-queue workflow composition for job chaining.

.. note::
    **Boundary with the optional provider:**

    This module provides *task-queue* oriented workflow composition —
    chaining background jobs with dependencies, branching, and retries.
    It is the Celery-style model: each step is a discrete task dispatched
    to a queue.

    ``the optional provider`` provides *business process* orchestration —
    multi-step pipelines, sagas, and bulk operations for in-process
    coordination. Use ``the optional provider module`` when you need
    synchronous in-process step pipelines; use this module when you need
    async, queue-backed job graphs.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
from dataclasses import dataclass, field
from enum import StrEnum
import time
from typing import TYPE_CHECKING, Any
import uuid

from quadkit.logging import get_logger
from quadkit.result import Err, Ok, Result

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from quadkit.tasks.workflows.state import WorkflowStateStore

logger = get_logger(__name__)


class WorkflowError(Exception):
    """Raised when a workflow execution fails unexpectedly."""

    _code: str = "QK_ERR_TASK_013"


class WorkflowStatus(StrEnum):
    """Enumeration of possible workflow execution states."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIALLY_COMPLETED = "partially_completed"


@dataclass
class StepResult:
    """Result from a single workflow step."""

    step_name: str
    success: bool
    data: Any = None
    error: str | None = None
    duration_ms: float = 0.0


@dataclass
class WorkflowResult:
    """Result from a complete workflow execution."""

    workflow_id: str
    status: WorkflowStatus
    steps: list[StepResult] = field(default_factory=list)
    final_result: Any = None
    total_duration_ms: float = 0.0
    error: str | None = None


@dataclass
class TaskStep:
    """A single step in a workflow.

    Args:
        name: Human-readable step name.
        handler: Async callable that takes input and returns output.
        on_error: Optional error handler.
        timeout: Optional timeout in seconds.
    """

    name: str
    handler: Callable[..., Awaitable[Any]]
    on_error: Callable[[Exception], Awaitable[Any]] | None = None
    timeout: float | None = None


class Workflow(ABC):
    """Abstract base for workflow patterns."""

    @abstractmethod
    async def execute(
        self, input_data: Any = None
    ) -> Result[WorkflowResult, WorkflowError]:
        """Execute the workflow with given input data."""


class TaskChain(Workflow):
    """Sequential task execution — output of each step feeds the next.

    Example:
        chain = TaskChain([
            TaskStep("parse", parse_data),
            TaskStep("validate", validate_data),
            TaskStep("save", save_data),
        ])
        result = await chain.execute(raw_input)
    """

    def __init__(
        self,
        steps: list[TaskStep],
        *,
        stop_on_error: bool = True,
        state_store: WorkflowStateStore | None = None,
        workflow_id: str | None = None,
    ) -> None:
        self.steps = steps
        self.stop_on_error = stop_on_error
        self._state_store = state_store
        self._workflow_id = workflow_id

    async def execute(
        self, input_data: Any = None
    ) -> Result[WorkflowResult, WorkflowError]:
        """Execute all steps in sequence, threading output of each step into the next.

        If a ``workflow_id`` and ``state_store`` were provided at construction,
        this method will attempt to resume from the last saved checkpoint — any
        step whose name appears in the persisted state's completed steps will be
        skipped, and the last completed step's output will seed the next step.
        """
        workflow_id = self._workflow_id or str(uuid.uuid4())[:8]
        result = WorkflowResult(
            workflow_id=workflow_id,
            status=WorkflowStatus.RUNNING,
        )
        start = time.monotonic()
        current_data = input_data

        # Resume support: skip already-completed steps from a prior run.
        completed_step_names: set[str] = set()
        if self._state_store and self._workflow_id:
            saved = await self._state_store.load_state(self._workflow_id)
            if saved is not None:
                completed_step_names = {s.step_name for s in saved.steps if s.success}
                result.steps = list(saved.steps)
                # Seed current_data from the last successful step's output.
                successful = [s for s in saved.steps if s.success]
                if successful:
                    current_data = successful[-1].data
                logger.info(
                    "workflow.resuming",
                    workflow_id=workflow_id,
                    skipping=list(completed_step_names),
                )

        try:
            for step in self.steps:
                if step.name in completed_step_names:
                    continue
                step_start = time.monotonic()
                try:
                    if step.timeout:
                        current_data = await asyncio.wait_for(
                            step.handler(current_data),
                            timeout=step.timeout,
                        )
                    else:
                        current_data = await step.handler(current_data)

                    step_result = StepResult(
                        step_name=step.name,
                        success=True,
                        data=current_data,
                        duration_ms=(time.monotonic() - step_start) * 1000,
                    )
                    result.steps.append(step_result)
                    if self._state_store:
                        await self._state_store.save_state(workflow_id, result)
                except Exception as exc:  # noqa: BLE001 — step-failure boundary
                    # ANY handler error (incl. timeouts via wait_for and
                    # non-stdlib exceptions) fails this step, not the whole
                    # workflow.
                    error_msg = str(exc)
                    step_result = StepResult(
                        step_name=step.name,
                        success=False,
                        error=error_msg,
                        duration_ms=(time.monotonic() - step_start) * 1000,
                    )
                    result.steps.append(step_result)
                    logger.warning(
                        "Chain step '%s' failed: %s",
                        step.name,
                        error_msg,
                    )

                    if step.on_error:
                        try:
                            current_data = await step.on_error(exc)
                        except Exception:  # noqa: BLE001 — handler isolation
                            logger.exception(
                                "Error handler for '%s' also failed",
                                step.name,
                            )

                    if self.stop_on_error:
                        result.status = WorkflowStatus.FAILED
                        result.error = f"Step '{step.name}' failed: {error_msg}"
                        if self._state_store:
                            await self._state_store.save_state(workflow_id, result)
                        break

            if result.status != WorkflowStatus.FAILED:
                result.status = WorkflowStatus.COMPLETED
                result.final_result = current_data

            result.total_duration_ms = (time.monotonic() - start) * 1000
            if self._state_store:
                await self._state_store.save_state(workflow_id, result)
            return Ok(result)
        except Exception as exc:
            logger.exception("Unexpected error in TaskChain execution")
            return Err(WorkflowError(str(exc)))

    def __or__(self, other: TaskStep) -> TaskChain:
        """PipeProtocol operator: chain | step.

        Preserves the resume wiring (``state_store`` / ``workflow_id``) so a
        piped chain checkpoints exactly like the original.
        """
        return TaskChain(
            [*self.steps, other],
            stop_on_error=self.stop_on_error,
            state_store=self._state_store,
            workflow_id=self._workflow_id,
        )


class TaskGroup(Workflow):
    """Parallel task execution — all steps run concurrently.

    Example:
        group = TaskGroup([
            TaskStep("email", send_email),
            TaskStep("sms", send_sms),
        ])
        result = await group.execute(user_data)
    """

    def __init__(
        self,
        steps: list[TaskStep],
        *,
        max_concurrency: int | None = None,
        state_store: WorkflowStateStore | None = None,
        workflow_id: str | None = None,
    ) -> None:
        self.steps = steps
        self.max_concurrency = max_concurrency
        self._state_store = state_store
        self._workflow_id = workflow_id

    async def execute(
        self, input_data: Any = None
    ) -> Result[WorkflowResult, WorkflowError]:
        """Run all steps concurrently, respecting max_concurrency if set."""
        workflow_id = self._workflow_id or str(uuid.uuid4())[:8]
        result = WorkflowResult(
            workflow_id=workflow_id,
            status=WorkflowStatus.RUNNING,
        )
        start = time.monotonic()

        semaphore = (
            asyncio.Semaphore(self.max_concurrency) if self.max_concurrency else None
        )

        async def run_step(step: TaskStep) -> StepResult:
            async def _inner() -> StepResult:
                step_start = time.monotonic()
                try:
                    data = await step.handler(input_data)
                    return StepResult(
                        step_name=step.name,
                        success=True,
                        data=data,
                        duration_ms=(time.monotonic() - step_start) * 1000,
                    )
                except Exception as exc:  # noqa: BLE001 — step-failure boundary
                    # ANY handler error fails this step, not the whole group.
                    return StepResult(
                        step_name=step.name,
                        success=False,
                        error=str(exc),
                        duration_ms=(time.monotonic() - step_start) * 1000,
                    )

            if semaphore:
                async with semaphore:
                    return await _inner()
            return await _inner()

        try:
            step_results = await asyncio.gather(
                *(run_step(s) for s in self.steps),
            )
            result.steps = list(step_results)

            all_ok = all(s.success for s in result.steps)
            any_ok = any(s.success for s in result.steps)

            if all_ok:
                result.status = WorkflowStatus.COMPLETED
                result.final_result = [s.data for s in result.steps]
            elif any_ok:
                result.status = WorkflowStatus.PARTIALLY_COMPLETED
            else:
                result.status = WorkflowStatus.FAILED
                result.error = "All steps failed"

            result.total_duration_ms = (time.monotonic() - start) * 1000
            if self._state_store:
                await self._state_store.save_state(workflow_id, result)
            return Ok(result)
        except Exception as exc:
            logger.exception("Unexpected error in TaskGroup execution")
            return Err(WorkflowError(str(exc)))


class TaskChord(Workflow):
    """Fan-out then collect — parallel steps + callback with all results.

    Example:
        chord = TaskChord(
            steps=[TaskStep("a", fetch_a), TaskStep("b", fetch_b)],
            callback=TaskStep("merge", merge_results),
        )
        result = await chord.execute()
    """

    def __init__(
        self,
        steps: list[TaskStep],
        callback: TaskStep,
    ) -> None:
        self.group = TaskGroup(steps)
        self.callback = callback

    async def execute(
        self, input_data: Any = None
    ) -> Result[WorkflowResult, WorkflowError]:
        """Fan out to all group steps then call the callback with their collected results."""
        try:
            group_result_wrapped = await self.group.execute(input_data)
            if group_result_wrapped.is_err():
                return group_result_wrapped

            group_result = group_result_wrapped.unwrap()

            if group_result.status == WorkflowStatus.FAILED:
                return Ok(group_result)

            # Pass collected results to callback
            step_start = time.monotonic()
            try:
                final = await self.callback.handler(group_result.final_result)
                group_result.steps.append(
                    StepResult(
                        step_name=self.callback.name,
                        success=True,
                        data=final,
                        duration_ms=(time.monotonic() - step_start) * 1000,
                    ),
                )
                group_result.final_result = final
                group_result.status = WorkflowStatus.COMPLETED
            except Exception as exc:  # noqa: BLE001 — step-failure boundary
                # ANY callback error fails the callback step, not the whole
                # chord (which already ran its group).
                group_result.steps.append(
                    StepResult(
                        step_name=self.callback.name,
                        success=False,
                        error=str(exc),
                        duration_ms=(time.monotonic() - step_start) * 1000,
                    ),
                )
                group_result.status = WorkflowStatus.FAILED
                group_result.error = f"Callback '{self.callback.name}' failed"

            return Ok(group_result)
        except Exception as exc:
            logger.exception("Unexpected error in TaskChord execution")
            return Err(WorkflowError(str(exc)))


class BranchStep(Workflow):
    """Branch based on a condition evaluated against the input.

    Example:
        workflow = BranchStep(
            condition=lambda data: data["amount"] > 1000,
            if_true=TaskStep("manual_review", manual_review),
            if_false=TaskStep("auto_approve", auto_approve),
        )
    """

    def __init__(
        self,
        condition: Callable[[Any], bool],
        if_true: TaskStep,
        if_false: TaskStep,
    ) -> None:
        self.condition = condition
        self.if_true = if_true
        self.if_false = if_false

    async def execute(
        self, input_data: Any = None
    ) -> Result[WorkflowResult, WorkflowError]:
        """Evaluate the condition and execute either the true or false branch."""
        workflow_id = str(uuid.uuid4())[:8]
        start = time.monotonic()

        try:
            step = self.if_true if self.condition(input_data) else self.if_false

            step_start = time.monotonic()
            try:
                data = await step.handler(input_data)
                step_result = StepResult(
                    step_name=step.name,
                    success=True,
                    data=data,
                    duration_ms=(time.monotonic() - step_start) * 1000,
                )
                return Ok(
                    WorkflowResult(
                        workflow_id=workflow_id,
                        status=WorkflowStatus.COMPLETED,
                        steps=[step_result],
                        final_result=data,
                        total_duration_ms=(time.monotonic() - start) * 1000,
                    )
                )
            except Exception as exc:  # noqa: BLE001 — step-failure boundary
                # ANY handler error fails the chosen branch step.
                step_result = StepResult(
                    step_name=step.name,
                    success=False,
                    error=str(exc),
                    duration_ms=(time.monotonic() - step_start) * 1000,
                )
                return Ok(
                    WorkflowResult(
                        workflow_id=workflow_id,
                        status=WorkflowStatus.FAILED,
                        steps=[step_result],
                        error=str(exc),
                        total_duration_ms=(time.monotonic() - start) * 1000,
                    )
                )
        except Exception as exc:
            logger.exception("Unexpected error in BranchStep execution")
            return Err(WorkflowError(str(exc)))


from quadkit.tasks.workflows.factories import chain as chain  # noqa: E402
