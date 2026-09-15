"""Tests for additional contracts types."""

import pytest

from quadkit.contracts.events.outbox import OutboxStatus
from quadkit.contracts.workflow.protocols import SagaState


class TestOutboxStatus:
    """Tests for OutboxStatus enum."""

    def test_outbox_status_values(self) -> None:
        """Test OutboxStatus enum values."""
        assert OutboxStatus.PENDING.value == "pending"
        assert OutboxStatus.PUBLISHED.value == "published"
        assert OutboxStatus.FAILED.value == "failed"

    def test_outbox_status_members(self) -> None:
        """Test OutboxStatus has expected members."""
        members = list(OutboxStatus)
        assert len(members) == 3


class TestSagaState:
    """Tests for SagaState enum."""

    def test_saga_state_values(self) -> None:
        """Test SagaState enum values."""
        assert SagaState.PENDING.value == "pending"
        assert SagaState.RUNNING.value == "running"
        assert SagaState.COMPENSATING.value == "compensating"
        assert SagaState.COMPLETED.value == "completed"
        assert SagaState.FAILED.value == "failed"

    def test_saga_state_members(self) -> None:
        """Test SagaState has expected members."""
        members = list(SagaState)
        assert len(members) == 5
