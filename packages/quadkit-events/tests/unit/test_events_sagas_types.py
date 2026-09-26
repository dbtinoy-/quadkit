"""Tests for events saga types."""

import pytest
from datetime import datetime, timezone

from quadkit.events.sagas.types import SagaRecord, SagaStatus, SagaStepRecord, SagaStepStatus


class TestSagaStatus:
    """Tests for SagaStatus enum."""

    def test_saga_status_values(self) -> None:
        """Test SagaStatus enum values."""
        assert SagaStatus.PENDING.value == "pending"
        assert SagaStatus.RUNNING.value == "running"
        assert SagaStatus.COMPLETED.value == "completed"
        assert SagaStatus.COMPENSATING.value == "compensating"
        assert SagaStatus.COMPENSATED.value == "compensated"
        assert SagaStatus.FAILED.value == "failed"

    def test_saga_status_members(self) -> None:
        """Test SagaStatus has expected members."""
        members = list(SagaStatus)
        assert len(members) == 6


class TestSagaStepStatus:
    """Tests for SagaStepStatus enum."""

    def test_saga_step_status_values(self) -> None:
        """Test SagaStepStatus enum values."""
        assert SagaStepStatus.PENDING.value == "pending"
        assert SagaStepStatus.RUNNING.value == "running"
        assert SagaStepStatus.COMPLETED.value == "completed"
        assert SagaStepStatus.COMPENSATING.value == "compensating"
        assert SagaStepStatus.COMPENSATED.value == "compensated"
        assert SagaStepStatus.FAILED.value == "failed"

    def test_saga_step_status_members(self) -> None:
        """Test SagaStepStatus has expected members."""
        members = list(SagaStepStatus)
        assert len(members) == 6


class TestSagaStepRecord:
    """Tests for SagaStepRecord dataclass."""

    def test_saga_step_record_defaults(self) -> None:
        """Test SagaStepRecord default values."""
        record = SagaStepRecord(step_name="step1")
        assert record.step_name == "step1"
        assert record.status == SagaStepStatus.PENDING
        assert record.started_at is None
        assert record.output == {}
        assert record.error is None
        assert record.attempts == 0


class TestSagaRecord:
    """Tests for SagaRecord dataclass."""

    def test_saga_record_defaults(self) -> None:
        """Test SagaRecord default values."""
        record = SagaRecord(saga_id="saga-1", saga_name="test-saga")
        assert record.saga_id == "saga-1"
        assert record.saga_name == "test-saga"
        assert record.status == SagaStatus.PENDING
        assert record.data == {}
        assert record.steps == {}

    def test_saga_record_with_steps(self) -> None:
        """Test SagaRecord with steps."""
        step = SagaStepRecord(step_name="step1")
        record = SagaRecord(
            saga_id="saga-1",
            saga_name="test",
            steps={"step1": step},
        )
        assert "step1" in record.steps
