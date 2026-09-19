"""Tests for core pipeline types."""

import pytest

from quadkit.primitives.pipeline import PipelineContext, StepExecutionResult, StepStatus


class TestStepStatus:
    """Tests for StepStatus enum."""

    def test_step_status_values(self) -> None:
        """Test StepStatus enum values."""
        assert StepStatus.PENDING.value == "pending"
        assert StepStatus.RUNNING.value == "running"
        assert StepStatus.COMPLETED.value == "completed"
        assert StepStatus.FAILED.value == "failed"
        assert StepStatus.SKIPPED.value == "skipped"

    def test_step_status_members(self) -> None:
        """Test StepStatus has expected members."""
        members = list(StepStatus)
        assert len(members) == 5

    def test_step_status_order(self) -> None:
        """Test StepStatus ordering by value."""
        # StrEnum members don't support direct comparison; compare values instead
        status_order = [
            StepStatus.PENDING,
            StepStatus.RUNNING,
            StepStatus.COMPLETED,
            StepStatus.FAILED,
            StepStatus.SKIPPED,
        ]
        assert status_order[0] == StepStatus.PENDING
        assert status_order[1] == StepStatus.RUNNING
        assert status_order[2] == StepStatus.COMPLETED


class TestStepExecutionResult:
    """Tests for StepExecutionResult dataclass."""

    def test_step_execution_result_defaults(self) -> None:
        """Test StepExecutionResult default values."""
        result = StepExecutionResult(
            step_name="test_step",
            status=StepStatus.PENDING,
        )
        assert result.step_name == "test_step"
        assert result.status == StepStatus.PENDING
        assert result.result is None
        assert result.error is None
        assert result.duration is None

    def test_step_execution_result_with_result(self) -> None:
        """Test StepExecutionResult with result."""
        result = StepExecutionResult(
            step_name="test_step",
            status=StepStatus.COMPLETED,
            result="success",
            duration=1.5,
        )
        assert result.result == "success"
        assert result.duration == 1.5

    def test_step_execution_result_with_error(self) -> None:
        """Test StepExecutionResult with error."""
        error = ValueError("Test error")
        result = StepExecutionResult(
            step_name="test_step",
            status=StepStatus.FAILED,
            error=error,
        )
        assert result.error is error


class TestPipelineContext:
    """Tests for PipelineContext dataclass."""

    def test_pipeline_context_defaults(self) -> None:
        """Test PipelineContext default values."""
        ctx = PipelineContext(pipeline_name="test_pipeline")
        assert ctx.step_results == {}
        assert ctx.metadata == {}

    def test_pipeline_context_with_values(self) -> None:
        """Test PipelineContext with values."""
        step_result = StepExecutionResult(
            step_name="step1",
            status=StepStatus.COMPLETED,
        )
        ctx = PipelineContext(
            pipeline_name="test_pipeline",
            step_results={"step1": "result1"},
            metadata={"key": "value"},
        )
        assert ctx.pipeline_name == "test_pipeline"
        assert ctx.step_results == {"step1": "result1"}
        assert ctx.metadata == {"key": "value"}
