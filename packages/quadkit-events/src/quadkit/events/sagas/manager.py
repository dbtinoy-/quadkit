"""Simple, sequential saga coordination manager.

``SagaManagerProtocol`` is the **recommended starting point** for implementing the SagaProtocol
pattern in most applications.  It executes a saga's steps one at a time in the
order they are defined, automatically retrying transient failures and running
compensating transactions in reverse order if any step fails.

Usage guide
-----------
* Register saga classes (subclasses of :class:`~quadkit.events.sagas.base.SagaBase`)
  via :meth:`SagaManagerProtocol.register`.
* Start a saga with :meth:`SagaManagerProtocol.start`; execution runs in a managed
  background ``asyncio.Task``.
* Poll the current state through :meth:`SagaManagerProtocol.get`.

Relationship to ``SagaOrchestrator``
--------------------------------------
``SagaManagerProtocol`` handles the common case: **sequential steps, single compensation
chain, automatic retries**.  When the business process requires *parallel*
step execution, *conditional transitions* between steps, or *state-machine-style*
flow control, use
:class:`~quadkit.events.sagas.orchestrator.SagaOrchestrator` instead.

Decision table:

+--------------------------------------------+--------------------+----------------------+
| Need                                       | Use                | Module               |
+============================================+====================+======================+
| Sequential steps, simple compensation     | ``SagaManagerProtocol``    | ``sagas.manager``    |
+--------------------------------------------+--------------------+----------------------+
| Parallel steps, conditional transitions   | ``SagaOrchestrator`` | ``sagas.orchestrator`` |
+--------------------------------------------+--------------------+----------------------+

Start with ``SagaManagerProtocol`` and migrate to ``SagaOrchestrator`` only when the
orchestration requirements outgrow the sequential model.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
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

if TYPE_CHECKING:
    from quadkit.events.sagas.base import SagaBase, SagaStep

logger = get_logger(__name__)


class SagaManagerProtocol:
    """Orchestrates saga execution, retries, and compensation."""

    def __init__(self, store: SagaStore | None = None) -> None:
        self._store: SagaStore = store or InMemorySagaStore()
        self._factories: dict[str, type[SagaBase]] = {}
        self._background_tasks: set[asyncio.Task] = set()

    def register(self, saga_class: type[SagaBase]) -> None:
        """Register a saga class by its name."""
        name = saga_class.name
        if not name:
            raise ValueError(f"{saga_class.__name__}.name must be set")
        self._factories[name] = saga_class
        logger.debug("Registered saga: %s", name)

    async def start(
        self,
        saga_name: str,
        data: dict[str, Any] | None = None,
        saga_id: str | None = None,
    ) -> str:
        """Start a new saga execution."""
        if saga_name not in self._factories:
            raise KeyError(f"No saga registered with name '{saga_name}'")

        saga_id = saga_id or str(uuid4())
        record = SagaRecord(
            saga_id=saga_id,
            saga_name=saga_name,
            status=SagaStatus.PENDING,
            data=data or {},
        )
        await self._store.save(record)

        create_tracked_task(
            self._run(saga_id),
            self._background_tasks,
            name=f"saga_{saga_id}",
        )
        return saga_id

    async def get(self, saga_id: str) -> SagaRecord | None:
        """Get the current state of a saga."""
        return await self._store.load(saga_id)

    async def _run(self, saga_id: str) -> None:
        """Internal: execute all saga steps in order."""
        record = await self._store.load(saga_id)
        if record is None:
            logger.error("SagaProtocol %s not found", saga_id)
            return

        saga_class = self._factories.get(record.saga_name)
        if saga_class is None:
            logger.error("No factory for saga %s", record.saga_name)
            return

        saga = saga_class()
        steps = saga._get_steps()
        ctx = SagaContext(
            saga_id=saga_id,
            saga_name=record.saga_name,
            data=dict(record.data),
        )

        record.status = SagaStatus.RUNNING
        await self._store.save(record)

        completed_steps: list[SagaStep] = []

        for step in steps:
            step_record = SagaStepRecord(step_name=step.name)
            record.steps[step.name] = step_record

            result = await self._execute_step(step, ctx, step_record)

            if result.success:
                step_record.status = SagaStepStatus.COMPLETED
                step_record.output = result.output
                ctx.step_results[step.name] = result.output
                completed_steps.append(step)
                await self._store.save(record)
            else:
                step_record.status = SagaStepStatus.FAILED
                step_record.error = result.error
                record.error = result.error
                await self._store.save(record)

                # Compensate all completed steps in reverse
                await self._compensate(completed_steps, ctx, record)
                return

        record.status = SagaStatus.COMPLETED
        record.completed_at = datetime.now(UTC)
        await self._store.save(record)
        logger.info("SagaProtocol %s completed successfully", saga_id)

    async def _execute_step(
        self,
        step: SagaStep,
        ctx: SagaContext,
        step_record: SagaStepRecord,
    ) -> SagaStepResult:
        """Execute a single step with retries."""
        step_record.status = SagaStepStatus.RUNNING
        step_record.started_at = datetime.now(UTC)

        last_error = ""
        for attempt in range(step.max_retries + 1):
            step_record.attempts = attempt + 1
            try:
                result = await step.action(ctx)
                step_record.completed_at = datetime.now(UTC)
                return result  # type: ignore[return-value]
            except Exception as exc:  # noqa: BLE001 — a raising step must become a failed step, never abort the saga (CancelledError still propagates)
                last_error = str(exc)
                logger.warning(
                    "SagaProtocol step %s attempt %d failed: %s",
                    step.name,
                    attempt + 1,
                    exc,
                )
                if attempt < step.max_retries:
                    await asyncio.sleep(step.retry_delay)

        return SagaStepResult.fail(last_error or "Max retries exceeded")

    async def _compensate(
        self,
        completed_steps: list[SagaStep],
        ctx: SagaContext,
        record: SagaRecord,
    ) -> None:
        """Run compensation for completed steps in reverse order."""
        record.status = SagaStatus.COMPENSATING
        await self._store.save(record)

        for step in reversed(completed_steps):
            if step.compensation is None:
                logger.warning("No compensation for step %s", step.name)
                continue

            step_record = record.steps.get(step.name)
            if step_record:
                step_record.status = SagaStepStatus.COMPENSATING

            try:
                compensation_result: Any = await step.compensation(ctx)  # type: ignore[func-returns-value]
                if step_record:
                    step_record.status = (
                        SagaStepStatus.COMPENSATED
                        if compensation_result is not None
                        and compensation_result.success
                        else SagaStepStatus.FAILED
                    )
            except Exception:  # noqa: BLE001 — every compensation must be attempted; one failure must not skip the rest
                logger.exception("Compensation for %s failed", step.name)
                if step_record:
                    step_record.status = SagaStepStatus.FAILED

            await self._store.save(record)

        record.status = SagaStatus.COMPENSATED
        await self._store.save(record)
        logger.info("SagaProtocol %s compensated", record.saga_id)
