"""Tests for tasks module."""

from __future__ import annotations

from quadkit.di.module import DynamicModule
from quadkit.tasks import TasksModule


class TestTasksModule:
    def test_tasks_module_exists(self) -> None:
        assert TasksModule is not None

    def test_configure_with_defaults(self) -> None:
        result = TasksModule.configure()
        assert isinstance(result, DynamicModule)
        assert result.module is TasksModule

    def test_configure_exports_task_queue(self) -> None:
        from quadkit.contracts.infra.tasks import TaskQueueProtocol

        result = TasksModule.configure()
        assert TaskQueueProtocol in result.exports

    def test_configure_exports_task_executor(self) -> None:
        from quadkit.contracts.infra.tasks import TaskExecutorProtocol

        result = TasksModule.configure()
        assert TaskExecutorProtocol in result.exports

    def test_configure_with_custom_worker_count(self) -> None:
        result = TasksModule.configure(worker_count=4)
        assert isinstance(result, DynamicModule)

    def test_configure_with_scheduler_disabled(self) -> None:
        result = TasksModule.configure(enable_scheduler=False)
        assert isinstance(result, DynamicModule)

    def test_configure_passes_task_discovery_roots(self) -> None:
        result = TasksModule.configure(
            task_modules=["app.tasks.cleanup_task"],
            task_packages=["app.tasks"],
        )

        provider = result.providers[0]
        assert provider._task_modules == ("app.tasks.cleanup_task",)  # noqa: SLF001
        assert provider._task_packages == ("app.tasks",)  # noqa: SLF001
