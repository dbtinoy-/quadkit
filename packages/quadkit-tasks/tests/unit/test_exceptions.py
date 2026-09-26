"""Tests for tasks exceptions."""


from quadkit.tasks.exceptions import (
    DuplicateTaskError,
    TaskCancelledError,
    TaskDependencyCycleError,
    TaskError,
    TaskExecutionError,
    TaskNotFoundError,
    TaskTimeoutError,
    TaskValidationError,
)
from quadkit.tasks.types import PoolStrategy, Priority


class TestTaskError:
    """Tests for TaskError base exception."""

    def test_task_error_message(self) -> None:
        """Test TaskError message."""
        err = TaskError("Task error occurred")
        assert err.message == "Task error occurred"


class TestTaskNotFoundError:
    """Tests for TaskNotFoundError."""

    def test_task_not_found_error(self) -> None:
        """Test TaskNotFoundError can be instantiated."""
        err = TaskNotFoundError("Task not found")
        assert err.message == "Task not found"


class TestTaskTimeoutError:
    """Tests for TaskTimeoutError."""

    def test_task_timeout_error(self) -> None:
        """Test TaskTimeoutError can be instantiated."""
        err = TaskTimeoutError("Task timed out")
        assert err.message == "Task timed out"


class TestTaskCancelledError:
    """Tests for TaskCancelledError."""

    def test_task_cancelled_error(self) -> None:
        """Test TaskCancelledError can be instantiated."""
        err = TaskCancelledError("Task cancelled")
        assert err.message == "Task cancelled"


class TestTaskExecutionError:
    """Tests for TaskExecutionError."""

    def test_task_execution_error(self) -> None:
        """Test TaskExecutionError can be instantiated."""
        err = TaskExecutionError("Task failed")
        assert err.message == "Task failed"

    def test_task_execution_error_with_original_error(self) -> None:
        """Test TaskExecutionError with original error."""
        original = ValueError("original error")
        err = TaskExecutionError("Task failed", original_error=original)
        assert err.original_error == original

    def test_task_execution_error_with_details(self) -> None:
        """Test TaskExecutionError with details."""
        err = TaskExecutionError("Task failed", details={"task_id": "123"})
        assert err.details["task_id"] == "123"


class TestTaskValidationError:
    """Tests for TaskValidationError."""

    def test_task_validation_error(self) -> None:
        """Test TaskValidationError can be instantiated."""
        err = TaskValidationError("Invalid task")
        assert err.message == "Invalid task"


class TestDuplicateTaskError:
    """Tests for DuplicateTaskError."""

    def test_duplicate_task_error(self) -> None:
        """Test DuplicateTaskError can be instantiated."""
        err = DuplicateTaskError("Duplicate task")
        assert err.message == "Duplicate task"


class TestTaskDependencyCycleError:
    """Tests for TaskDependencyCycleError."""

    def test_dependency_cycle_error(self) -> None:
        """Test TaskDependencyCycleError stores cycle."""
        cycle = ["A", "B", "C", "A"]
        err = TaskDependencyCycleError(cycle)
        assert err.cycle == cycle

    def test_dependency_cycle_error_message(self) -> None:
        """Test TaskDependencyCycleError generates correct message."""
        cycle = ["A", "B", "C", "A"]
        err = TaskDependencyCycleError(cycle)
        assert "Task dependency cycle detected" in err.message
        assert "A → B → C → A" in err.message


class TestPriority:
    """Tests for Priority enum."""

    def test_priority_values(self) -> None:
        """Test Priority enum values."""
        assert Priority.LOW == 0
        assert Priority.NORMAL == 5
        assert Priority.HIGH == 10
        assert Priority.CRITICAL == 20

    def test_priority_comparison(self) -> None:
        """Test Priority comparison works."""
        assert Priority.CRITICAL > Priority.HIGH
        assert Priority.HIGH > Priority.NORMAL
        assert Priority.NORMAL > Priority.LOW


class TestPoolStrategy:
    """Tests for PoolStrategy enum."""

    def test_pool_strategy_values(self) -> None:
        """Test PoolStrategy enum values."""
        assert PoolStrategy.FIXED.value == "fixed"
        assert PoolStrategy.DYNAMIC.value == "dynamic"
        assert PoolStrategy.ADAPTIVE.value == "adaptive"


class TestTaskRegistrationError:
    """Tests for TaskRegistrationError exception."""

    def test_task_registration_error_import(self) -> None:
        """Test TaskRegistrationError can be imported."""
        from quadkit.tasks.exceptions import TaskRegistrationError

        err = TaskRegistrationError("bad task")
        assert err.message == "bad task"

    def test_task_registration_error_is_quadkit_error(self) -> None:
        """Test TaskRegistrationError is a QuadkitError."""
        from quadkit.contracts.exceptions import QuadkitError
        from quadkit.tasks.exceptions import TaskRegistrationError

        err = TaskRegistrationError("bad task")
        assert isinstance(err, QuadkitError)

    def test_task_registration_error_code(self) -> None:
        """Test TaskRegistrationError has correct code."""
        from quadkit.tasks.exceptions import TaskRegistrationError

        err = TaskRegistrationError("bad task")
        assert err.code == "QK_ERR_TASK_011"
