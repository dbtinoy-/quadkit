"""Tests for tasks workflow types."""

import pytest

from quadkit.tasks.workflows.core import StepResult, WorkflowError, WorkflowStatus


class TestWorkflowStatus:
    """Tests for WorkflowStatus enum."""

    def test_workflow_status_values(self) -> None:
        """Test WorkflowStatus enum values."""
        assert WorkflowStatus.PENDING.value == "pending"
        assert WorkflowStatus.RUNNING.value == "running"
        assert WorkflowStatus.COMPLETED.value == "completed"
        assert WorkflowStatus.FAILED.value == "failed"
        assert WorkflowStatus.PARTIALLY_COMPLETED.value == "partially_completed"

    def test_workflow_status_members(self) -> None:
        """Test WorkflowStatus has expected members."""
        members = list(WorkflowStatus)
        assert len(members) == 5


class TestStepResult:
    """Tests for StepResult dataclass."""

    def test_step_result_defaults(self) -> None:
        """Test StepResult default values."""
        result = StepResult(step_name="test", success=True)
        assert result.step_name == "test"
        assert result.success is True
        assert result.data is None
        assert result.error is None
        assert result.duration_ms == 0.0

    def test_step_result_with_data(self) -> None:
        """Test StepResult with data."""
        result = StepResult(
            step_name="test",
            success=True,
            data={"key": "value"},
        )
        assert result.data == {"key": "value"}

    def test_step_result_with_error(self) -> None:
        """Test StepResult with error."""
        result = StepResult(
            step_name="test",
            success=False,
            error="Something went wrong",
        )
        assert result.error == "Something went wrong"
