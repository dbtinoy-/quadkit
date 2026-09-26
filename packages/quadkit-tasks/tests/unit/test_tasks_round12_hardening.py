"""Round-12 hardening tests: worker/workflow failure boundaries, lock-held
error, dialect placeholder translation, Postgres nack semantics."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.tasks.backends.postgres import (
    PostgresTaskConfig,
    PostgresTaskQueue,
)
from quadkit.tasks.concurrency.locking import LockManager, distributed_lock
from quadkit.tasks.dialect import translate_placeholders
from quadkit.tasks.exceptions import TaskLockHeldError
from quadkit.tasks.models.job import JobProtocol
from quadkit.tasks.workflows.core import (
    StepResult,
    TaskChain,
    TaskStep,
    WorkflowResult,
    WorkflowStatus,
)
from quadkit.tasks.workflows.state import DatabaseWorkflowStateStore

from quadkit.tasks.workflows.state import InMemoryWorkflowStateStore  # noqa: F401

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


# ---------------------------------------------------------------------------
# Fake database providers
# ---------------------------------------------------------------------------


class _FakeQueryResult:
    rows: list[Any] = []


class _RecordingProvider:
    """DatabaseProviderProtocol fake that records executed SQL.

    ``name`` mirrors the dialect attribute on real providers
    (e.g. PostgresProvider.name == "postgres").
    """

    name = "postgres"

    def __init__(self) -> None:
        self.executed: list[str] = []

    async def execute(self, sql: str, params: list[Any] | None = None) -> None:
        self.executed.append(sql)

    async def execute_query(
        self, sql: str, params: list[Any] | None = None
    ) -> _FakeQueryResult:
        self.executed.append(sql)
        return _FakeQueryResult()

    def scoped_context(self) -> "_ScopedCtx":
        return _ScopedCtx()

    async def get_scoped_connection(self) -> "_RecordingProvider":
        return self


class _ScopedCtx:
    async def __aenter__(self) -> "_ScopedCtx":
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None


def _running_result() -> WorkflowResult:
    return WorkflowResult(
        workflow_id="w1",
        status=WorkflowStatus.RUNNING,
        steps=[
            StepResult(
                step_name="s1", success=True, data={"k": "v"}, duration_ms=1.0
            ),
        ],
    )


# ---------------------------------------------------------------------------
# Worker: ANY handler error must land in the failure path
# ---------------------------------------------------------------------------


class TestWorkerFailureBoundary:
    @pytest.mark.asyncio
    async def test_attribute_error_does_not_escape_execute_job(self) -> None:
        from quadkit.tasks.execution.worker import TaskWorker

        async def bad_handler() -> None:
            raise AttributeError("missing attribute")

        services = MagicMock()
        # No optional services: keep the failure path free of side effects.
        for attr in (
            "idempotency_manager",
            "dead_letter_queue",
            "result_store",
            "progress_store",
            "dashboard",
            "task_manager",
            "retry_policy",
            "hooks",
            "logger",
            "container",
        ):
            setattr(services, attr, None)
        queue = AsyncMock()
        queue.enqueue = AsyncMock()
        worker = TaskWorker("w1", queue, {"bad": bad_handler}, services=services)

        job = JobProtocol(id="j-1", name="bad")
        result = await worker._execute_job(job)

        assert result.is_err()
        # The job must be marked failed, not stuck in RUNNING.
        assert job.status.value == "failed"


# ---------------------------------------------------------------------------
# Workflows: step failure must not escalate to the whole workflow
# ---------------------------------------------------------------------------


class TestWorkflowStepBoundary:
    @pytest.mark.asyncio
    async def test_attribute_error_fails_step_not_chain(self) -> None:
        async def broken(data: object) -> object:
            raise AttributeError("nope")

        async def never_reached(data: object) -> object:
            raise AssertionError("must not run after stop_on_error")

        async def ok(data: object) -> object:
            return data

        chain = TaskChain(
            [
                TaskStep("ok", ok),
                TaskStep("broken", broken),
                TaskStep("next", never_reached),
            ],
            stop_on_error=True,
        )
        result = await chain.execute("in")
        assert result.is_ok()
        workflow = result.unwrap()
        assert workflow.status == WorkflowStatus.FAILED
        assert [s.step_name for s in workflow.steps] == ["ok", "broken"]
        assert workflow.steps[1].success is False
        assert "nope" in (workflow.steps[1].error or "")

    @pytest.mark.asyncio
    async def test_or_operator_preserves_resume_wiring(self) -> None:
        from quadkit.tasks.workflows.state import InMemoryWorkflowStateStore

        store = InMemoryWorkflowStateStore()
        wf_id = "wf-resume-1"

        async def step_a(data: object) -> object:
            return data

        base = TaskChain(
            [TaskStep("a", step_a)],
            state_store=store,
            workflow_id=wf_id,
        )
        piped = base | TaskStep("b", step_a)
        assert piped._state_store is store
        assert piped._workflow_id == wf_id
        assert [s.name for s in piped.steps] == ["a", "b"]


# ---------------------------------------------------------------------------
# Locks: distributed_lock must raise when the key is held
# ---------------------------------------------------------------------------


class TestDistributedLockHeld:
    @pytest.mark.asyncio
    async def test_raises_when_key_already_held(self) -> None:
        manager = LockManager()
        first = manager.acquire("held:key", timeout=60)
        assert await first.acquire()

        with pytest.raises(TaskLockHeldError):
            async with distributed_lock("held:key", lock_manager=manager):
                pass  # must not be reached

        await first.release()


# ---------------------------------------------------------------------------
# Dialect placeholder translation
# ---------------------------------------------------------------------------


class TestDialectTranslation:
    def test_postgres_numbered_placeholders(self) -> None:
        sql = "SELECT ? FROM t WHERE a = ? AND b = ?"
        assert translate_placeholders(sql, "postgres") == (
            "SELECT $1 FROM t WHERE a = $2 AND b = $3"
        )

    def test_mysql_percent_placeholders(self) -> None:
        assert translate_placeholders("SELECT ?", "mysql") == "SELECT %s"

    def test_sqlite_and_unknown_pass_through(self) -> None:
        assert translate_placeholders("SELECT ?", "sqlite") == "SELECT ?"
        assert translate_placeholders("SELECT ?", "") == "SELECT ?"
        assert translate_placeholders("SELECT ?", "weird") == "SELECT ?"

    @pytest.mark.asyncio
    async def test_workflow_state_store_translates_for_postgres(self) -> None:
        provider = _RecordingProvider()
        store = DatabaseWorkflowStateStore(provider)
        await store.save_state("w1", _running_result())

        assert provider.executed
        for sql in provider.executed:
            assert "?" not in sql
        # The upsert (last statement) carries the translated placeholders.
        assert "$1" in provider.executed[-1]

    @pytest.mark.asyncio
    async def test_scheduler_store_translates_for_postgres(self) -> None:
        from quadkit.tasks.scheduling.persistence import DatabaseSchedulerStore
        from quadkit.tasks.scheduling.scheduler import ScheduledJob
        from quadkit.tasks.scheduling.templates import JobTemplateProtocol

        provider = _RecordingProvider()
        store = DatabaseSchedulerStore(provider)
        job = ScheduledJob(
            job_template=JobTemplateProtocol(name="x"),
            cron_expression="0 0 * * *",
            next_run=123.0,
        )
        await store.save_job("j1", job)

        assert provider.executed
        for sql in provider.executed:
            assert "?" not in sql
        assert "$1" in provider.executed[-1]


# ---------------------------------------------------------------------------
# Postgres backend: nack semantics + ping robustness
# ---------------------------------------------------------------------------


class TestPostgresNackSemantics:
    @pytest.mark.asyncio
    async def test_nack_requeue_false_marks_failed(self) -> None:
        provider = _RecordingProvider()
        queue = PostgresTaskQueue(
            config=PostgresTaskConfig(table="tasks"), provider=provider
        )
        await queue.nack("job-1", requeue=False)

        sql = provider.executed[-1]
        assert "status = 'failed'" in sql
        # A negative INTERVAL delay (the old behaviour) meant immediately
        # available — the opposite of "do not requeue".
        assert "INTERVAL" not in sql

    @pytest.mark.asyncio
    async def test_nack_requeue_true_uses_delay_clause(self) -> None:
        provider = _RecordingProvider()
        queue = PostgresTaskQueue(
            config=PostgresTaskConfig(table="tasks"), provider=provider
        )
        await queue.nack("job-1", requeue=True)

        sql = provider.executed[-1]
        assert "status = 'pending'" in sql
        assert "INTERVAL" in sql

    @pytest.mark.asyncio
    async def test_ping_reports_false_on_driver_error(self) -> None:
        provider = _RecordingProvider()

        async def boom(*_a: object, **_k: object) -> None:
            raise RuntimeError("connection refused")

        provider.execute = boom  # type: ignore[method-assign]
        queue = PostgresTaskQueue(
            config=PostgresTaskConfig(table="tasks"), provider=provider
        )
        assert await queue.ping() is False


# ---------------------------------------------------------------------------
# Middleware chain: any handler error -> failed JobResult + after-hooks run
# ---------------------------------------------------------------------------


class TestMiddlewareFailureBoundary:
    @pytest.mark.asyncio
    async def test_attribute_error_yields_failed_result_and_after_hooks_run(self) -> None:
        from quadkit.tasks.execution._middleware_chain import (
            execute_handler_through_middleware,
        )
        from quadkit.tasks.middleware.core import (
            TaskExecutionContext,
            TaskMiddleware,
            TaskMiddlewarePipeline,
        )

        observed: list[str] = []

        class Watcher(TaskMiddleware):
            async def after_execute(self, ctx: TaskExecutionContext) -> None:
                observed.append(
                    "fail" if ctx.result is not None and not ctx.result.success
                    else "other",
                )

        async def broken() -> None:
            raise AttributeError("boom")

        pipeline = TaskMiddlewarePipeline()
        pipeline.add(Watcher())

        async def resolve(_h, args, kwargs):
            return list(args), dict(kwargs)

        job = JobProtocol(id="j-mw", name="mw_job")
        result = await execute_handler_through_middleware(
            pipeline, broken, job, resolve
        )

        assert result.success is False
        assert "boom" in (result.error or "")
        # after-hook observed the failure (previously it never ran).
        assert observed == ["fail"]

    @pytest.mark.asyncio
    async def test_timeout_middleware_catches_any_error(self) -> None:
        from quadkit.tasks.middleware.core import (
            TaskExecutionContext,
            TimeoutMiddleware,
        )

        async def broken() -> None:
            raise KeyError("missing")

        middleware = TimeoutMiddleware(default_timeout=5.0)
        ctx = TaskExecutionContext(job=JobProtocol(id="j-t", name="t"))
        result = await middleware.execute_with_timeout(broken, ctx.job, ctx)

        assert result.success is False
        assert "missing" in (result.error or "")
