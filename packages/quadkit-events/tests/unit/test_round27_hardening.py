"""Round 27 hardening pins.

Covers the gap-hunt fixes from the quadkit-events audit — the same
defect class closed in rounds 17/22 (storage/audit/core): narrow
``(RuntimeError, TypeError, ValueError, OSError)`` tuples in saga,
bus, dispatch, and streaming paths where a foreign error type
aborted loops, left sagas stuck, or escaped unwrapped.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from quadkit.events.sagas.context import SagaContext, SagaStepResult
from quadkit.events.sagas.manager import SagaManagerProtocol
from quadkit.events.sagas.orchestrator import (
    OrchestratedStep,
    SagaOrchestrator,
)
from quadkit.events.sagas.store import InMemorySagaStore
from quadkit.events.sagas.types import (
    SagaRecord,
    SagaStepRecord,
    SagaStepStatus,
    SagaStatus,
)


class TestSagaManagerForeignErrors:
    @pytest.mark.asyncio
    async def test_raising_step_becomes_failed_step(self) -> None:
        manager = SagaManagerProtocol(store=InMemorySagaStore())

        async def _boom(ctx: Any) -> None:
            raise KeyError("step exploded")

        step = SimpleNamespace(
            name="step1", action=_boom, max_retries=0, retry_delay=0.0
        )
        step_record = SagaStepRecord("step1")

        # A step raising a foreign type must return a failed result,
        # not propagate out of the saga executor.
        result = await manager._execute_step(step, SagaContext("s1", "s"), step_record)

        assert result.success is False
        assert "step exploded" in (result.error or "")

    @pytest.mark.asyncio
    async def test_all_compensations_attempted_on_foreign_error(self) -> None:
        manager = SagaManagerProtocol(store=InMemorySagaStore())
        store = InMemorySagaStore()
        manager = SagaManagerProtocol(store=store)

        calls: list[str] = []

        async def _comp1(ctx: Any) -> None:
            raise KeyError("compensation exploded")

        async def _comp2(ctx: Any) -> None:
            calls.append("comp2")

        steps = [
            SimpleNamespace(name="step2", compensation=_comp2),
            SimpleNamespace(name="step1", compensation=_comp1),
        ]
        record = SagaRecord(
            saga_id="s1",
            saga_name="s",
            status=SagaStatus.FAILED,
            data={},
        )
        record.steps["step1"] = SagaStepRecord("step1")
        record.steps["step2"] = SagaStepRecord("step2")
        await store.save(record)

        await manager._compensate(steps, SagaContext("s1", "s"), record)

        # step1's compensation raised a foreign type; step2's must still run.
        assert calls == ["comp2"]


class TestSagaOrchestratorForeignErrors:
    @pytest.mark.asyncio
    async def test_foreign_step_error_records_failed(self) -> None:
        store = InMemorySagaStore()
        orchestrator = SagaOrchestrator(store=store)

        class _Action:
            async def execute(self, ctx: Any) -> SagaStepResult:
                raise KeyError("action exploded")

            async def compensate(self, ctx: Any) -> SagaStepResult:
                return SagaStepResult.Ok({})

        orchestrator.define("s1", [OrchestratedStep(name="step1", action=_Action())])
        saga_id = await orchestrator.start("s1")
        await asyncio.sleep(0.05)

        record = await store.load(saga_id)
        assert record is not None
        # The saga must reach a terminal status with the step failure
        # recorded — never left stuck in PENDING/RUNNING.
        assert record.status in {
            SagaStatus.COMPENSATED,
            SagaStatus.FAILED,
        }
        step_record = record.steps.get("step1")
        assert step_record is not None
        assert step_record.status == SagaStepStatus.FAILED
        assert "action exploded" in (step_record.error or "")

    @pytest.mark.asyncio
    async def test_all_compensations_attempted_on_foreign_error(self) -> None:
        store = InMemorySagaStore()
        orchestrator = SagaOrchestrator(store=store)

        calls: list[str] = []

        class _GoodAction:
            async def execute(self, ctx: Any) -> SagaStepResult:
                return SagaStepResult.Ok({})

            async def compensate(self, ctx: Any) -> SagaStepResult:
                calls.append("good")
                return SagaStepResult.Ok({})

        class _BadAction:
            async def execute(self, ctx: Any) -> SagaStepResult:
                return SagaStepResult.Ok({})

            async def compensate(self, ctx: Any) -> SagaStepResult:
                raise KeyError("compensation exploded")

        record = SagaRecord(
            saga_id="s1",
            saga_name="s",
            status=SagaStatus.FAILED,
            data={},
        )
        record.steps["good"] = SagaStepRecord("good")
        record.steps["bad"] = SagaStepRecord("bad")
        await store.save(record)

        await orchestrator._compensate(
            ["good", "bad"],
            {"good": OrchestratedStep(name="good", action=_GoodAction()),
             "bad": OrchestratedStep(name="bad", action=_BadAction())},
            SagaContext("s1", "s"),
            record,
        )

        # "bad" compensates first (reverse order) and raises; "good" must still run.
        assert calls == ["good"]


class TestBusForeignErrors:
    @pytest.mark.asyncio
    async def test_command_foreign_error_wrapped(self) -> None:
        from quadkit.events.buses import CommandBusImpl
        from quadkit.events.buses.command import CommandExecutionError
        from quadkit.events.messages import Command

        bus = CommandBusImpl()
        handler = AsyncMock(side_effect=KeyError("handler exploded"))
        bus.register(Command, handler)

        with pytest.raises(CommandExecutionError) as exc_info:
            await bus.dispatch(Command())

        assert "handler exploded" in exc_info.value.error

    @pytest.mark.asyncio
    async def test_query_foreign_error_wrapped(self) -> None:
        from quadkit.events.buses import QueryBusImpl
        from quadkit.events.buses.query import QueryExecutionError
        from quadkit.events.messages import Query

        bus = QueryBusImpl()
        handler = AsyncMock(side_effect=KeyError("handler exploded"))
        bus.register(Query, handler)

        with pytest.raises(QueryExecutionError) as exc_info:
            await bus.execute(Query())

        assert "handler exploded" in exc_info.value.error


class TestStreamDispatcherIsolation:
    @pytest.mark.asyncio
    async def test_sequential_delivery_survives_foreign_handler_error(self) -> None:
        from quadkit.events.streaming.dispatcher import StreamDispatcher

        dispatcher = StreamDispatcher(parallel_delivery=False, continue_on_error=True)
        calls: list[str] = []

        async def _bad(event: Any) -> None:
            raise KeyError("handler exploded")

        async def _good(event: Any) -> None:
            calls.append("good")

        # _bad raises a foreign type first; _good must still be delivered.
        await dispatcher._deliver_sequential(object(), [_bad, _good])

        assert calls == ["good"]
        assert dispatcher._stats.events_failed == 1
