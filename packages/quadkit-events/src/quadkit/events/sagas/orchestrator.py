"""Advanced saga orchestration with parallel steps and state machine transitions.

``SagaOrchestrator`` handles **complex, non-sequential saga flows** where steps
can run in *parallel*, transitions between steps are *conditional*, and failure
routing requires *explicit on-failure targets*.  It is the right tool when the
simpler :class:`~quadkit.events.sagas.manager.SagaManagerProtocol` (sequential,
single-chain) is insufficient.

Key capabilities
----------------
* **Parallel execution** — define sibling steps inside
  :attr:`OrchestratedStep.parallel`; they are executed concurrently via
  ``asyncio.gather`` and their results are merged before advancing.
* **Conditional transitions** — each :class:`OrchestratedStep` carries a
  ``next_step`` (success path) and an ``on_failure`` (failure path), forming a
  directed graph rather than a linear list.
* **Graph-based compensation** — completed steps are compensated in reverse
  order of completion across the entire executed sub-graph.

Relationship to ``SagaManagerProtocol``
---------------------------------
:class:`~quadkit.events.sagas.manager.SagaManagerProtocol` is the **recommended
starting point** for most saga implementations.  It is simpler to configure and
covers the majority of use cases (sequential steps with automatic retries and
compensation).  Migrate to ``SagaOrchestrator`` only when the orchestration
requirements are explicitly non-sequential or require parallel compensation
branches.

Quick comparison:

+--------------------------------------------+--------------------+----------------------+
| Need                                       | Use                | Module               |
+============================================+====================+======================+
| Sequential steps, simple compensation     | ``SagaManagerProtocol``    | ``sagas.manager``    |
+--------------------------------------------+--------------------+----------------------+
| Parallel steps, conditional transitions   | ``SagaOrchestrator`` | ``sagas.orchestrator`` |
+--------------------------------------------+--------------------+----------------------+
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable
from uuid import uuid4

from quadkit.concurrency.task_utils import create_tracked_task
from quadkit.events.sagas.context import SagaContext, SagaStepResult
from quadkit.events.sagas.store import InMemorySagaStore, SagaStore
from quadkit.events.sagas.types import (
    SagaRecord,
    SagaStatus,
    SagaStepRecord,
    SagaStepStatus,
)
from quadkit.logging import get_logger

logger = get_logger(__name__)


@runtime_checkable
class SagaAction(Protocol):
    """Protocol for a saga action/step."""

    async def execute(self, ctx: SagaContext) -> SagaStepResult:
        """Execute the action."""
        ...

    async def compensate(self, ctx: SagaContext) -> SagaStepResult:
        """Compensate the action if it fails or saga aborts."""
        ...


@dataclass
class OrchestratedStep:
    """A step within an orchestrated saga."""

    name: str
    action: SagaAction
    next_step: str | None = None
    on_failure: str | None = None  # Transition to another step on failure
    parallel: list[OrchestratedStep] = field(default_factory=list)


class SagaOrchestrator:
    """Manages complex saga executions with parallel steps and transitions.

    This is an evolution of SagaManagerProtocol that handles non-sequential flows.
    """

    def __init__(self, store: SagaStore | None = None) -> None:
        self._store: SagaStore = store or InMemorySagaStore()
        self._definitions: dict[str, dict[str, OrchestratedStep]] = {}
        self._background_tasks: set[asyncio.Task] = set()

    def define(self, saga_name: str, steps: list[OrchestratedStep]) -> None:
        """Define a saga structure."""
        self._definitions[saga_name] = {s.name: s for s in steps}

    async def start(
        self,
        saga_name: str,
        data: dict[str, Any] | None = None,
    ) -> str:
        """Start a new orchestrated saga."""
        if saga_name not in self._definitions:
            raise KeyError(f"No saga definition for '{saga_name}'")

        saga_id = str(uuid4())
        record = SagaRecord(
            saga_id=saga_id,
            saga_name=saga_name,
            status=SagaStatus.PENDING,
            data=data or {},
        )
        await self._store.save(record)

        # Start execution in background
        create_tracked_task(
            self._execute(saga_id),
            self._background_tasks,
            name=f"saga_{saga_id}",
        )
        return saga_id

    async def _execute(self, saga_id: str) -> None:
        """Execute the saga flow."""
        record = await self._store.load(saga_id)
        if not record:
            return

        steps_map = self._definitions[record.saga_name]
        ctx = SagaContext(record.saga_id, record.saga_name, dict(record.data))

        record.status = SagaStatus.RUNNING
        await self._store.save(record)

        # Start with the first step (we assume first in list is start)
        current_step_name = next(iter(steps_map.keys()))
        completed_steps: list[str] = []

        try:
            while current_step_name:
                step = steps_map[current_step_name]
                step_record = record.steps.get(
                    step.name, SagaStepRecord(step_name=step.name)
                )
                record.steps[step.name] = step_record

                result = await self._run_step(step, ctx, step_record)
                await self._store.save(record)

                if result.success:
                    completed_steps.append(step.name)
                    ctx.step_results[step.name] = result.output
                    current_step_name = step.next_step  # type: ignore[assignment]
                elif step.on_failure:
                    current_step_name = step.on_failure
                else:
                    # Unhandled failure, start compensation
                    await self._compensate(completed_steps, steps_map, ctx, record)
                    return

            record.status = SagaStatus.COMPLETED
            record.completed_at = datetime.now(UTC)
            await self._store.save(record)

        except Exception as e:  # noqa: BLE001 — any orchestration failure must record FAILED, never leave the saga stuck RUNNING
            logger.exception("Orchestrator failed for saga %s", saga_id)
            record.status = SagaStatus.FAILED
            record.error = str(e)
            await self._store.save(record)

    async def _run_step(
        self,
        step: OrchestratedStep,
        ctx: SagaContext,
        record: SagaStepRecord,
    ) -> SagaStepResult:
        """Run a step (potentially in parallel)."""
        record.status = SagaStepStatus.RUNNING
        record.started_at = datetime.now(UTC)

        if step.parallel:
            # Execute multiple sub-steps in parallel
            results = await asyncio.gather(
                *[
                    self._run_step(s, ctx, SagaStepRecord(s.name))
                    for s in step.parallel
                ],
                return_exceptions=True,
            )

            # Combine results
            success = all(isinstance(r, SagaStepResult) and r.success for r in results)
            combined_output = {}
            errors = []

            for r in results:
                if isinstance(r, SagaStepResult):
                    combined_output.update(r.output)
                    if not r.success:
                        errors.append(r.error)
                else:
                    errors.append(str(r))

            record.completed_at = datetime.now(UTC)
            if success:
                record.status = SagaStepStatus.COMPLETED
                record.output = combined_output
                return SagaStepResult.Ok(combined_output)
            record.status = SagaStepStatus.FAILED
            record.error = "; ".join(filter(None, errors))
            return SagaStepResult.fail(record.error)

        # Sequential single action
        try:
            result = await step.action.execute(ctx)
            record.completed_at = datetime.now(UTC)
            record.status = (
                SagaStepStatus.COMPLETED if result.success else SagaStepStatus.FAILED
            )
            record.output = result.output
            record.error = result.error
            return result
        except Exception as e:  # noqa: BLE001 — a raising step is a failed step, never a saga abort
            record.status = SagaStepStatus.FAILED
            record.error = str(e)
            return SagaStepResult.fail(str(e))

    async def _compensate(
        self,
        step_names: list[str],
        steps_map: dict[str, OrchestratedStep],
        ctx: SagaContext,
        record: SagaRecord,
    ) -> None:
        """Compensate all completed steps in reverse order."""
        record.status = SagaStatus.COMPENSATING
        await self._store.save(record)

        for name in reversed(step_names):
            step = steps_map[name]
            step_record = record.steps.get(name)
            if step_record:
                step_record.status = SagaStepStatus.COMPENSATING
                await self._store.save(record)

            try:
                await step.action.compensate(ctx)
                if step_record:
                    step_record.status = SagaStepStatus.COMPENSATED
            except Exception as e:  # noqa: BLE001 — every compensation must be attempted; one failure must not skip the rest
                logger.error("Compensation failed for step %s: %s", name, e)
                if step_record:
                    step_record.status = SagaStepStatus.FAILED

            await self._store.save(record)

        record.status = SagaStatus.COMPENSATED
        await self._store.save(record)
