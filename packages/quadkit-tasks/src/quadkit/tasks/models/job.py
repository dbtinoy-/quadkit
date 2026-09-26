"""JobProtocol model and status tracking for Quadkit Tasks

This module provides the JobProtocol model which represents executable work units
with comprehensive status tracking and metadata management.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Any
import uuid

# Import JobStatus from root types.py - Single source of truth
from quadkit.contracts.infra.tasks import JobStatus


@dataclass
class JobResult:
    """Result of a job execution

    Captures the outcome of job execution including success status,
    return data, error information, and performance metrics.
    """

    success: bool
    data: Any = None
    error: str | None = None
    duration: float = 0.0
    retry_count: int = 0
    id: str | None = None
    name: str | None = None
    completed_at: float | None = None
    failed_at: float | None = None

    @classmethod
    def ok(cls, data: Any = None, duration: float = 0.0) -> JobResult:
        """Create a successful result

        Args:
            data: Return value from the job
            duration: Execution duration in seconds

        Returns:
            JobResult with success=True
        """
        return cls(success=True, data=data, duration=duration)

    @classmethod
    def fail(cls, error: str, retry_count: int = 0, duration: float = 0.0) -> JobResult:
        """Create a failure result

        Args:
            error: Error message describing the failure
            retry_count: Number of retry attempts made
            duration: Execution duration in seconds

        Returns:
            JobResult with success=False
        """
        return cls(
            success=False,
            error=error,
            retry_count=retry_count,
            duration=duration,
            failed_at=time.time(),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary for serialization"""
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "duration": self.duration,
            "retry_count": self.retry_count,
            "id": self.id,
            "name": self.name,
            "completed_at": self.completed_at,
            "failed_at": self.failed_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> JobResult:
        """Create result from dictionary"""
        return cls(**data)


@dataclass
class JobProtocol:
    """Represents a background job with comprehensive status tracking

    Jobs are executable work units that can be queued, scheduled, tracked,
    and retried. They support priority ordering, dependency management,
    and timeout control.

    Attributes:
        id: Unique job identifier
        name: Human-readable job name/type
        args: Positional arguments for job handler
        kwargs: Keyword arguments for job handler
        priority: Execution priority (higher = more important)
        max_retries: Maximum retry attempts on failure
        timeout: Execution timeout in seconds
        depends_on: List of job IDs this job depends on
        status: Current job status
        created_at: Timestamp when job was created
        started_at: Timestamp when job started executing
        completed_at: Timestamp when job finished
        retry_count: Current number of retry attempts
        last_error: Most recent error message
        result: JobProtocol execution result
        scheduled_at: Timestamp for scheduled execution
        cron_expression: Cron expression for recurring jobs
    """

    id: str
    name: str
    args: tuple[Any, ...] = field(default_factory=tuple)
    kwargs: dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    max_retries: int = 3
    timeout: float | None = None
    depends_on: list[str] = field(default_factory=list)
    idempotency_key: str | None = None
    correlation_id: str | None = None
    causation_id: str | None = None

    # Status tracking
    status: JobStatus = JobStatus.PENDING
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    completed_at: float | None = None
    retry_count: int = 0
    last_error: str | None = None
    result: JobResult | None = None

    # Scheduling
    scheduled_at: float | None = None
    cron_expression: str | None = None

    def __post_init__(self) -> None:
        """Initialize job with generated ID if not provided"""
        if not self.id:
            self.id = str(uuid.uuid4())

    @property
    def is_pending(self) -> bool:
        """Check if job is pending execution"""
        return self.status == JobStatus.PENDING

    @property
    def is_running(self) -> bool:
        """Check if job is currently running"""
        return self.status == JobStatus.RUNNING

    @property
    def is_completed(self) -> bool:
        """Check if job completed successfully"""
        return self.status == JobStatus.COMPLETED

    @property
    def is_failed(self) -> bool:
        """Check if job failed"""
        return self.status == JobStatus.FAILED

    @property
    def can_retry(self) -> bool:
        """Check if job can be retried (hasn't exceeded max_retries)"""
        return self.retry_count < self.max_retries

    @property
    def duration_ms(self) -> float | None:
        """Get job execution duration in milliseconds"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at) * 1000
        return None

    def mark_running(self) -> None:
        """Mark job as running and record start time"""
        self.status = JobStatus.RUNNING
        self.started_at = time.time()

    def mark_completed(self, result: JobResult) -> None:
        """Mark job as completed with result

        Args:
            result: JobProtocol execution result
        """
        self.status = JobStatus.COMPLETED
        self.completed_at = time.time()
        self.result = result

    def mark_failed(self, error: str) -> None:
        """Mark job as failed with error message

        Args:
            error: Error message describing the failure
        """
        self.status = JobStatus.FAILED
        self.completed_at = time.time()
        self.last_error = error

    def mark_retrying(self) -> None:
        """Mark job as retrying and increment retry count"""
        self.status = JobStatus.RETRYING
        self.retry_count += 1

    def mark_cancelled(self) -> None:
        """Mark job as cancelled"""
        self.status = JobStatus.CANCELLED
        self.completed_at = time.time()

    def to_dict(self) -> dict[str, Any]:
        """Convert job to dictionary for serialization

        Returns:
            Dictionary representation of job
        """
        return {
            "id": self.id,
            "name": self.name,
            "args": self.args,
            "kwargs": self.kwargs,
            "priority": self.priority,
            "max_retries": self.max_retries,
            "timeout": self.timeout,
            "depends_on": self.depends_on,
            "idempotency_key": self.idempotency_key,
            "status": self.status.value,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "retry_count": self.retry_count,
            "last_error": self.last_error,
            "result": self.result.to_dict() if self.result else None,
            "scheduled_at": self.scheduled_at,
            "cron_expression": self.cron_expression,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> JobProtocol:
        """Create job from dictionary

        Args:
            data: Dictionary representation of job

        Returns:
            JobProtocol instance
        """
        # Convert status string back to enum
        data["status"] = JobStatus(data["status"])

        # Convert result if present
        if data.get("result"):
            data["result"] = JobResult.from_dict(data["result"])

        return cls(**data)

    def __lt__(self, other: JobProtocol) -> bool:
        """Compare jobs for priority queue (higher priority first)

        Args:
            other: JobProtocol to compare with

        Returns:
            True if this job has lower priority or was created later
        """
        if not isinstance(other, JobProtocol):
            return NotImplemented
        return (-self.priority, self.created_at) < (-other.priority, other.created_at)
