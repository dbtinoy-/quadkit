"""Tests for TaskProvider.register_scheduled_task atomicity."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.tasks.di.provider import TaskProvider
from quadkit.tasks.exceptions import TaskRegistrationError


@pytest.fixture
def mock_queue() -> MagicMock:
    """Create a mock queue."""
    queue = MagicMock()
    queue.enqueue = AsyncMock()
    return queue


@pytest.fixture
def task_provider(mock_queue: MagicMock) -> TaskProvider:
    """Create a TaskProvider with mocked dependencies."""
    provider = TaskProvider(queue=mock_queue)
    provider.registry = MagicMock()
    provider._scheduler = MagicMock()
    provider.enable_scheduler = True
    provider.schedule_job_sync = MagicMock()
    return provider


class TestRegisterScheduledTask:
    """Tests for atomic register_scheduled_task."""

    def test_missing_task_name_raises(self, task_provider: TaskProvider) -> None:
        """Test missing _task_name raises TaskRegistrationError."""
        def bad():  # no _task_name attribute
            pass

        with pytest.raises(TaskRegistrationError, match="_task_name"):
            task_provider.register_scheduled_task(bad)

    def test_missing_cron_raises(self, task_provider: TaskProvider) -> None:
        """Test missing _cron raises TaskRegistrationError when scheduler enabled."""
        task_provider.enable_scheduler = True

        def fn():
            pass

        fn._task_name = "test-task"
        # No _cron attribute

        with pytest.raises(TaskRegistrationError, match="_cron"):
            task_provider.register_scheduled_task(fn)

    def test_atomic_rollback_on_schedule_failure(
        self, task_provider: TaskProvider
    ) -> None:
        """Test registration rolled back when scheduling fails."""

        def fn():
            pass

        fn._task_name = "test-task"
        fn._cron = "* * * * *"
        fn.signature = MagicMock(return_value=MagicMock())

        # Make scheduler raise
        task_provider.schedule_job_sync = MagicMock(
            side_effect=RuntimeError("scheduler boom")
        )

        with pytest.raises(RuntimeError, match="scheduler boom"):
            task_provider.register_scheduled_task(fn)

        # Verify unregister was called to rollback
        task_provider.registry.unregister.assert_called_once_with("test-task")

    def test_happy_path(self, task_provider: TaskProvider) -> None:
        """Test successful registration schedules the task."""

        def fn():
            pass

        fn._task_name = "test-task"
        fn._cron = "* * * * *"
        fn.signature = MagicMock(return_value=MagicMock())

        task_provider.register_scheduled_task(fn)

        task_provider.registry.register.assert_called_once_with("test-task", fn)
        task_provider.schedule_job_sync.assert_called_once()
