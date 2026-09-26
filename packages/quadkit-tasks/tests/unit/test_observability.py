"""Tests for task observability."""

import pytest
import time

from quadkit.tasks.observability.core import (
    TaskDashboard,
    ExecutionRecord,
)


class TestExecutionRecord:
    """Tests for ExecutionRecord."""

    def test_create_record(self):
        """Test creating an execution record."""
        record = ExecutionRecord(
            job_id="job-1",
            task_name="send_email",
            success=True,
            duration_ms=150.5,
        )

        assert record.job_id == "job-1"
        assert record.task_name == "send_email"
        assert record.success is True
        assert record.duration_ms == 150.5
        assert record.error is None
        assert record.worker_id is None

    def test_create_record_with_error(self):
        """Test creating a failed execution record."""
        record = ExecutionRecord(
            job_id="job-1",
            task_name="send_email",
            success=False,
            duration_ms=50.0,
            error="SMTP connection failed",
        )

        assert record.success is False
        assert record.error == "SMTP connection failed"

    def test_to_dict(self):
        """Test serialization to dictionary."""
        record = ExecutionRecord(
            job_id="job-1",
            task_name="send_email",
            success=True,
            duration_ms=150.5,
            worker_id="worker-1",
        )

        d = record.to_dict()
        assert d["job_id"] == "job-1"
        assert d["task_name"] == "send_email"
        assert d["success"] is True
        assert d["duration_ms"] == 150.5
        assert d["worker_id"] == "worker-1"


class TestTaskDashboard:
    """Tests for TaskDashboard."""

    def test_create_dashboard(self):
        """Test creating a dashboard."""
        dashboard = TaskDashboard(history_size=100, window_seconds=60)

        assert dashboard._history.maxlen == 100
        assert dashboard._window_seconds == 60
        assert dashboard._total_executed == 0
        assert dashboard._total_failed == 0

    def test_record_successful_execution(self):
        """Test recording a successful execution."""
        dashboard = TaskDashboard()
        dashboard.record_execution(
            task_name="send_email",
            job_id="job-1",
            duration_ms=150.0,
            success=True,
        )

        summary = dashboard.get_summary()
        assert summary["total_executed"] == 1
        assert summary["total_failed"] == 0
        assert summary["error_rate_pct"] == 0.0

    def test_record_failed_execution(self):
        """Test recording a failed execution."""
        dashboard = TaskDashboard()
        dashboard.record_execution(
            task_name="send_email",
            job_id="job-1",
            duration_ms=50.0,
            success=False,
            error="SMTP failed",
        )

        summary = dashboard.get_summary()
        assert summary["total_executed"] == 1
        assert summary["total_failed"] == 1
        assert summary["error_rate_pct"] == 100.0

    def test_multiple_task_types(self):
        """Test recording multiple task types."""
        dashboard = TaskDashboard()
        dashboard.record_execution("task_a", success=True)
        dashboard.record_execution("task_a", success=True)
        dashboard.record_execution("task_b", success=False)

        summary = dashboard.get_summary()
        assert summary["total_executed"] == 3
        assert summary["total_failed"] == 1
        assert summary["task_types"] == 2

    def test_get_summary_throughput(self):
        """Test throughput calculation."""
        dashboard = TaskDashboard()
        dashboard.record_execution("task", success=True)
        dashboard.record_execution("task", success=True)

        summary = dashboard.get_summary()
        assert summary["throughput_per_sec"] > 0

    def test_get_recent_executions(self):
        """Test getting recent executions."""
        dashboard = TaskDashboard()
        dashboard.record_execution("task_a", job_id="job-1", success=True)
        dashboard.record_execution("task_b", job_id="job-2", success=False)

        recent = dashboard.get_recent_executions(limit=10)
        assert len(recent) == 2

    def test_get_recent_executions_limit(self):
        """Test limiting recent executions."""
        dashboard = TaskDashboard(history_size=100)
        for i in range(50):
            dashboard.record_execution("task", job_id=f"job-{i}", success=True)

        recent = dashboard.get_recent_executions(limit=10)
        assert len(recent) == 10

    def test_history_size_limit(self):
        """Test that history respects size limit."""
        dashboard = TaskDashboard(history_size=5)
        for i in range(10):
            dashboard.record_execution("task", job_id=f"job-{i}", success=True)

        recent = dashboard.get_recent_executions(limit=10)
        assert len(recent) == 5

    def test_window_throughput(self):
        """Test window-based throughput."""
        dashboard = TaskDashboard(window_seconds=1)
        dashboard.record_execution("task", success=True)

        summary = dashboard.get_summary()
        assert summary["window_throughput_per_sec"] >= 0


