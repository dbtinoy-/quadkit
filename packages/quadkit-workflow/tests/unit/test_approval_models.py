"""Tests for workflow approval models."""

import pytest

from quadkit.workflow.approval.models import (
    ApprovalPolicy,
    ApprovalStatus,
    ApprovalStep,
)


class TestApprovalStatus:
    """Tests for ApprovalStatus enum."""

    def test_pending_value(self) -> None:
        assert ApprovalStatus.PENDING == "pending"

    def test_approved_value(self) -> None:
        assert ApprovalStatus.APPROVED == "approved"

    def test_rejected_value(self) -> None:
        assert ApprovalStatus.REJECTED == "rejected"

    def test_skipped_value(self) -> None:
        assert ApprovalStatus.SKIPPED == "skipped"


class TestApprovalPolicy:
    """Tests for ApprovalPolicy enum."""

    def test_all_value(self) -> None:
        assert ApprovalPolicy.ALL == "all"

    def test_any_value(self) -> None:
        assert ApprovalPolicy.ANY == "any"

    def test_majority_value(self) -> None:
        assert ApprovalPolicy.MAJORITY == "majority"


class TestApprovalStep:
    """Tests for ApprovalStep dataclass."""

    @pytest.mark.asyncio
    async def test_create_step(self) -> None:
        """Should create an approval step."""

        async def approver():
            return True

        step = ApprovalStep(name="test-step", approver=approver)
        assert step.name == "test-step"
        assert step.approver == approver
        assert step.condition is None
        assert step.metadata == {}

    @pytest.mark.asyncio
    async def test_create_step_with_condition(self) -> None:
        """Should create an approval step with condition."""

        async def approver():
            return True

        async def condition():
            return True

        step = ApprovalStep(
            name="test-step",
            approver=approver,
            condition=condition,
        )
        assert step.condition == condition

    @pytest.mark.asyncio
    async def test_create_step_with_metadata(self) -> None:
        """Should create an approval step with metadata."""

        async def approver():
            return True

        step = ApprovalStep(
            name="test-step",
            approver=approver,
            metadata={"key": "value"},
        )
        assert step.metadata == {"key": "value"}

    @pytest.mark.asyncio
    async def test_approver_returns_true(self) -> None:
        """Should execute approver and return True."""

        async def approver():
            return True

        step = ApprovalStep(name="test", approver=approver)
        result = await step.approver()
        assert result is True

    @pytest.mark.asyncio
    async def test_approver_returns_false(self) -> None:
        """Should execute approver and return False."""

        async def approver():
            return False

        step = ApprovalStep(name="test", approver=approver)
        result = await step.approver()
        assert result is False
