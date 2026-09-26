"""TASK-1: a decorated ``@scheduled`` function is live after app boot.

The entry described a scheduler that stays empty forever unless the application
itself calls ``register_scheduled_task()`` *after* boot. The framework does
discover decorated tasks now, from the module/package roots it is configured
with — but every existing test stops at ``TaskProvider.boot()``, so nothing
covered the path a user actually writes: ``TasksModule.configure(task_modules=
[...])`` on an ``Application``, boot it, read the schedule back.
"""

from __future__ import annotations

from pathlib import Path
import sys

import pytest

from quadkit.app import Application
from quadkit.tasks import MemoryTaskQueue, TasksModule
from quadkit.tasks.decorators import _clear_registered_tasks
from quadkit.tasks.di.provider import TaskProvider

PACKAGE_NAME = "sched_app"

MODULE_SOURCE = '''"""Scheduled jobs for the boot test."""

from quadkit.tasks import scheduled, task


@scheduled(cron="*/15 * * * *", name="cleanup")
async def cleanup() -> dict[str, bool]:
    return {"ok": True}


@task(name="send_confirmation")
async def send_confirmation(order_id: str) -> dict[str, str]:
    return {"order_id": order_id}
'''


def _write_package(tmp_path: Path) -> None:
    """Write a package whose module carries one scheduled and one plain task."""
    package = tmp_path / PACKAGE_NAME
    package.mkdir(parents=True, exist_ok=True)
    (package / "__init__.py").write_text("")
    (package / "jobs.py").write_text(MODULE_SOURCE)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "roots",
    [
        {"task_modules": [f"{PACKAGE_NAME}.jobs"]},
        {"task_packages": [PACKAGE_NAME]},
    ],
    ids=["module", "package"],
)
async def test_the_boot_registers_the_schedule_and_the_handler(
    tmp_path: Path, roots: dict[str, list[str]]
) -> None:
    """After boot the schedule is known and the handler is dispatchable."""
    _write_package(tmp_path)
    sys.path.insert(0, str(tmp_path))
    try:
        module = TasksModule.configure(
            queue=MemoryTaskQueue(),
            worker_count=1,
            enable_scheduler=True,
            **roots,
        )
        async with Application.boot(name="sched-app-test", modules=[module]) as app:
            provider = await app.container.resolve(TaskProvider)

            scheduled_jobs = provider.get_scheduled_jobs()
            assert scheduled_jobs is not None
            assert [
                (job["name"], job["cron"]) for job in scheduled_jobs["scheduled_jobs"]
            ] == [("cleanup", "*/15 * * * *")]

            # The schedule is only half of it: the body has to be callable
            # too, which is what the pool reads (TASK-4/TASK-5).
            handlers = provider.registry.to_dict()
            assert "cleanup" in handlers
            assert "send_confirmation" in handlers
    finally:
        _clear_registered_tasks((PACKAGE_NAME,))
        sys.modules.pop(f"{PACKAGE_NAME}.jobs", None)
        sys.modules.pop(PACKAGE_NAME, None)
        sys.path = [entry for entry in sys.path if entry != str(tmp_path)]


@pytest.mark.asyncio
async def test_an_imported_task_outside_the_configured_roots_is_not_scheduled(
    tmp_path: Path,
) -> None:
    """Discovery is bounded by the configured roots, not by what is imported.

    Without this, the test above would also pass if boot scanned every imported
    module — and a task the application never asked for would quietly get a
    schedule of its own.
    """
    _write_package(tmp_path)
    other = tmp_path / "other_app"
    other.mkdir()
    (other / "__init__.py").write_text("")
    (other / "jobs.py").write_text(
        "from quadkit.tasks import scheduled, task\n\n\n"
        '@scheduled(cron="0 3 * * *", name="other_cleanup")\n'
        "async def other_cleanup() -> None:\n"
        "    return None\n\n\n"
        '@task(name="not_mine")\n'
        "async def not_mine() -> None:\n"
        "    return None\n"
    )
    sys.path.insert(0, str(tmp_path))
    try:
        import other_app.jobs  # noqa: F401  (the decorators therefore ran)

        module = TasksModule.configure(
            queue=MemoryTaskQueue(),
            worker_count=1,
            enable_scheduler=True,
            task_modules=[f"{PACKAGE_NAME}.jobs"],
        )
        async with Application.boot(name="sched-scope-test", modules=[module]) as app:
            provider = await app.container.resolve(TaskProvider)

            assert set(provider.registry.to_dict()) == {
                "cleanup",
                "send_confirmation",
            }
            scheduled_jobs = provider.get_scheduled_jobs()
            assert scheduled_jobs is not None
            assert [
                (job["name"], job["cron"]) for job in scheduled_jobs["scheduled_jobs"]
            ] == [("cleanup", "*/15 * * * *")]
    finally:
        _clear_registered_tasks((PACKAGE_NAME, "other_app"))
        for name in (
            f"{PACKAGE_NAME}.jobs",
            PACKAGE_NAME,
            "other_app.jobs",
            "other_app",
        ):
            sys.modules.pop(name, None)
        sys.path = [entry for entry in sys.path if entry != str(tmp_path)]


@pytest.mark.asyncio
async def test_a_configured_root_that_does_not_import_fails_the_boot() -> None:
    """A misspelled root is a configuration error, not an empty discovery.

    ``import_task_modules`` imports what it is given, so a path that cannot be
    resolved surfaces at boot. That is deliberate — discovery that silently
    skips an unresolvable root would turn a typo into "my scheduled task never
    runs", which is the failure mode this entry is about.
    """
    module = TasksModule.configure(
        queue=MemoryTaskQueue(),
        worker_count=1,
        enable_scheduler=True,
        task_modules=["no_such_app_anywhere.jobs"],
    )

    with pytest.raises(ModuleNotFoundError):
        async with Application.boot(name="sched-missing-root-test", modules=[module]):
            pass  # pragma: no cover - the boot itself raises
