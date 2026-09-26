"""Tests for tasks exceptions."""

import pytest

from quadkit.tasks.exceptions import (
    DuplicateTaskError,
    QueueFullError,
    TaskCancelledError,
    TaskDependencyCycleError,
    TaskError,
    TaskExecutionError,
    TaskNotFoundError,
    TaskTimeoutError,
    TaskValidationError,
)


class TestTaskError:
    """Tests for TaskError base exception."""

    def test_task_error(self) -> None:
        """Test TaskError basic."""
        error = TaskError("Task error occurred")
        assert "Task error occurred" in str(error)


class TestTaskNotFoundError:
    """Tests for TaskNotFoundError."""

    def test_task_not_found_error(self) -> None:
        """Test TaskNotFoundError."""
        error = TaskNotFoundError()
        assert "not found" in str(error).lower() or "task" in str(error).lower()


class TestTaskTimeoutError:
    """Tests for TaskTimeoutError."""

    def test_task_timeout_error(self) -> None:
        """Test TaskTimeoutError."""
        error = TaskTimeoutError()
        assert "timeout" in str(error).lower() or "task" in str(error).lower()


class TestTaskCancelledError:
    """Tests for TaskCancelledError."""

    def test_task_cancelled_error(self) -> None:
        """Test TaskCancelledError."""
        error = TaskCancelledError()
        assert "cancelled" in str(error).lower() or "task" in str(error).lower()


class TestTaskExecutionError:
    """Tests for TaskExecutionError."""

    def test_task_execution_error(self) -> None:
        """Test TaskExecutionError basic."""
        error = TaskExecutionError("Task execution failed")
        assert "Task execution failed" in str(error)

    def test_task_execution_error_with_original(self) -> None:
        """Test TaskExecutionError with original error."""
        original = ValueError("Original error")
        error = TaskExecutionError("Failed", original_error=original)
        assert error.original_error is original


class TestTaskValidationError:
    """Tests for TaskValidationError."""

    def test_task_validation_error(self) -> None:
        """Test TaskValidationError."""
        error = TaskValidationError("Invalid task parameters")
        assert "Invalid task parameters" in str(error)


class TestDuplicateTaskError:
    """Tests for DuplicateTaskError."""

    def test_duplicate_task_error(self) -> None:
        """Test DuplicateTaskError."""
        error = DuplicateTaskError()
        assert "duplicate" in str(error).lower() or "task" in str(error).lower()


class TestTaskDependencyCycleError:
    """Tests for TaskDependencyCycleError."""

    def test_task_dependency_cycle_error(self) -> None:
        """Test TaskDependencyCycleError."""
        cycle = ["A", "B", "C", "A"]
        error = TaskDependencyCycleError(cycle=cycle)
        assert "cycle" in str(error).lower()
        assert error.cycle == cycle

    def test_task_dependency_cycle_error_message(self) -> None:
        """Test TaskDependencyCycleError contains cycle path."""
        cycle = ["job1", "job2", "job3", "job1"]
        error = TaskDependencyCycleError(cycle=cycle)
        assert "job1" in str(error)
        assert "job2" in str(error)

    def test_task_dependency_cycle_error_with_details(self) -> None:
        """Test TaskDependencyCycleError with additional details."""
        cycle = ["A", "B", "A"]
        error = TaskDependencyCycleError(
            cycle=cycle,
            details={"job_id": "123"},
        )
        assert error.cycle == cycle
        assert "cycle" in str(error).lower()

    def test_task_dependency_cycle_error_hints_remediation(self) -> None:
        """Test TaskDependencyCycleError provides remediation hint."""
        cycle = ["X", "Y", "X"]
        error = TaskDependencyCycleError(cycle=cycle)
        assert error.hint is not None
        assert "Remove" in error.hint or "break" in error.hint.lower()


class TestQueueFullError:
    """Tests for QueueFullError."""

    def test_queue_full_error_default(self) -> None:
        """Test QueueFullError with defaults."""
        error = QueueFullError()
        assert "queue" in str(error).lower() or "full" in str(error).lower()

    def test_queue_full_error_with_queue_name(self) -> None:
        """Test QueueFullError with queue name."""
        error = QueueFullError(queue_name="my-queue")
        assert error.details.get("queue_name") == "my-queue"

    def test_queue_full_error_with_capacity(self) -> None:
        """Test QueueFullError with capacity."""
        error = QueueFullError(capacity=1000)
        assert error.details.get("capacity") == 1000

    def test_queue_full_error_with_all_params(self) -> None:
        """Test QueueFullError with all parameters."""
        error = QueueFullError(
            message="Queue limit reached",
            queue_name="priority-queue",
            capacity=500,
        )
        assert "Queue limit reached" in str(error)
        assert error.details["queue_name"] == "priority-queue"
        assert error.details["capacity"] == 500
