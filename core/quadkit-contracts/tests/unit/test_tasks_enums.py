"""Tests for tasks enums."""

import pytest

from quadkit.contracts.infra.tasks.enums import JobStatus


class TestJobStatus:
    """Tests for JobStatus enum."""

    def test_pending_status(self) -> None:
        """Test pending status value."""
        assert JobStatus.PENDING.value == "pending"

    def test_running_status(self) -> None:
        """Test running status value."""
        assert JobStatus.RUNNING.value == "running"

    def test_completed_status(self) -> None:
        """Test completed status value."""
        assert JobStatus.COMPLETED.value == "completed"

    def test_failed_status(self) -> None:
        """Test failed status value."""
        assert JobStatus.FAILED.value == "failed"

    def test_retrying_status(self) -> None:
        """Test retrying status value."""
        assert JobStatus.RETRYING.value == "retrying"

    def test_cancelled_status(self) -> None:
        """Test cancelled status value."""
        assert JobStatus.CANCELLED.value == "cancelled"

    def test_all_statuses_defined(self) -> None:
        """Test all job statuses are defined."""
        statuses = list(JobStatus)
        assert len(statuses) == 6
        assert JobStatus.PENDING in statuses
        assert JobStatus.RUNNING in statuses
        assert JobStatus.COMPLETED in statuses
        assert JobStatus.FAILED in statuses
        assert JobStatus.RETRYING in statuses
        assert JobStatus.CANCELLED in statuses

    def test_status_is_string_enum(self) -> None:
        """Test that JobStatus is a string enum."""
        assert JobStatus.PENDING == "pending"
        assert JobStatus.RUNNING == "running"
        assert JobStatus.COMPLETED == "completed"
        assert JobStatus.FAILED == "failed"
        assert JobStatus.RETRYING == "retrying"
        assert JobStatus.CANCELLED == "cancelled"
