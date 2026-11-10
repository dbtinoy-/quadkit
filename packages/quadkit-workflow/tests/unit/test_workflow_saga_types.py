"""Tests for workflow types."""

import pytest
from collections.abc import Awaitable

from quadkit.workflow.types import (
    SagaStep,
    StepExecutionResult,
    StepStatus,
)


class TestStepStatus:
    """Tests for StepStatus enum."""

    def test_step_status_values(self) -> None:
        """Test StepStatus enum values."""
        assert StepStatus.PENDING is not None
        assert StepStatus.RUNNING is not None
        assert StepStatus.COMPLETED is not None
        assert StepStatus.FAILED is not None


class TestStepExecutionResult:
    """Tests for StepExecutionResult."""

    def test_step_execution_result_creation(self) -> None:
        """Test StepExecutionResult creation."""
        result = StepExecutionResult(
            step_name="test_step",
            status=StepStatus.COMPLETED,
        )
        assert result.step_name == "test_step"
        assert result.status == StepStatus.COMPLETED


class TestSagaStep:
    """Tests for SagaStep."""

    async def test_saga_step_basic(self) -> None:
        """Test SagaStep basic creation."""
        async def action() -> str:
            return "done"

        async def compensation() -> None:
            pass

        step = SagaStep(
            name="step1",
            action=action,
            compensation=compensation,
        )
        assert step.name == "step1"
        assert step.max_retries == 3
        assert step.retry_delay == 1.0

    def test_saga_step_defaults(self) -> None:
        """Test SagaStep default values."""
        async def action() -> str:
            return "done"

        step = SagaStep(name="step1", action=action)
        assert step.compensation is None
        assert step.max_retries == 3
        assert step.idempotent is False
