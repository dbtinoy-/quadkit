"""Tests for the migration scheduler's run_at handling."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from quadkit.events.schema.migration.scheduler import MigrationScheduler


class _FakeTaskManager:
    """Records created background tasks without running them."""

    def __init__(self) -> None:
        self.tasks: list[tuple[object, str]] = []

    @staticmethod
    def _close_unrun_coroutine(coro: object) -> None:
        """Dispose of coroutine objects because this fake never schedules them."""
        close = getattr(coro, "close", None)
        if callable(close):
            close()

    def create_background_task(
        self, coro: object, *, name: str | None = None
    ) -> object:
        self.tasks.append((coro, name or ""))
        self._close_unrun_coroutine(coro)
        return object()

    def create_critical_task(self, coro: object, *, name: str | None = None) -> object:
        self.tasks.append((coro, name or ""))
        self._close_unrun_coroutine(coro)
        return object()


def _make_scheduler() -> tuple[MigrationScheduler, _FakeTaskManager]:
    migrator = object()  # type: ignore[arg-type]
    task_manager = _FakeTaskManager()
    return MigrationScheduler(migrator, task_manager), task_manager  # type: ignore[arg-type]


class TestScheduleMigrationRunAt:
    def test_naive_future_run_at_does_not_raise(self) -> None:
        """The documented ``datetime.now() + timedelta(...)`` usage must not
        crash on the naive-vs-aware subtraction."""
        scheduler, tm = _make_scheduler()
        job_id = asyncio.run(
            scheduler.schedule_migration(
                version_map={"UserCreated": 3},
                run_at=datetime.now() + timedelta(hours=1),
            )
        )
        assert job_id
        assert len(tm.tasks) == 1  # delayed task created
        assert "delayed_migration" in tm.tasks[0][1]

    def test_aware_future_run_at_schedules_delayed(self) -> None:
        scheduler, tm = _make_scheduler()
        asyncio.run(
            scheduler.schedule_migration(
                version_map={"UserCreated": 3},
                run_at=datetime.now(UTC) + timedelta(hours=2),
            )
        )
        assert len(tm.tasks) == 1
        assert "delayed_migration" in tm.tasks[0][1]

    def test_past_run_at_runs_immediately(self) -> None:
        scheduler, tm = _make_scheduler()
        asyncio.run(
            scheduler.schedule_migration(
                version_map={"UserCreated": 3},
                run_at=datetime.now(UTC) - timedelta(hours=1),
            )
        )
        assert len(tm.tasks) == 1
        assert "migration_job_" in tm.tasks[0][1]
        assert "delayed_migration" not in tm.tasks[0][1]

    def test_none_run_at_runs_immediately(self) -> None:
        scheduler, tm = _make_scheduler()
        asyncio.run(scheduler.schedule_migration(version_map={"UserCreated": 3}))
        assert len(tm.tasks) == 1
        assert "migration_job_" in tm.tasks[0][1]
        assert "delayed_migration" not in tm.tasks[0][1]
