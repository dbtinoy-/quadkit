"""Bulk operation data models — enums, errors, and result dataclasses."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
import time
from typing import Any, Generic, TypeVar

from quadkit.contracts.exceptions import QuadkitError
from quadkit.logging import safe_error_type

T = TypeVar("T")
R = TypeVar("R")


class BulkOperationState(StrEnum):
    """States for bulk operations."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BulkOperationError(QuadkitError):
    """Base exception for bulk operation errors."""

    _code = "QK_ERR_WF_020"

    def __init__(
        self,
        message: str = "Bulk operation error",
    ) -> None:
        super().__init__(message)


class BulkOperationTimeoutError(BulkOperationError):
    """Raised when a bulk operation times out."""

    _code = "QK_ERR_WF_021"

    def __init__(self, message: str = "Bulk operation timed out") -> None:
        super().__init__(message)


class BulkOperationCancelledError(BulkOperationError):
    """Raised when a bulk operation is cancelled."""

    _code = "QK_ERR_WF_022"

    def __init__(self, message: str = "Bulk operation cancelled") -> None:
        super().__init__(message)


@dataclass
class BulkItemError:
    """Structured error information for a failed batch.

    Attributes:
        batch_id: The ID of the batch that failed.
        error: Human-readable error message.
        error_type: The fully-qualified type name of the exception.
        retry_count: Number of retry attempts made before giving up.
        timestamp: Monotonic timestamp of the failure.
    """

    batch_id: int
    error: str
    error_type: str
    retry_count: int
    timestamp: float


@dataclass
class BulkOperationMetrics:
    """Metrics for bulk operations."""

    total_items: int = 0
    processed_items: int = 0
    successful_items: int = 0
    failed_items: int = 0
    total_batches: int = 0
    completed_batches: int = 0
    failed_batches: int = 0
    start_time: float | None = None
    end_time: float | None = None
    total_retries: int = 0
    average_batch_time: float = 0.0
    errors: list[BulkItemError] = field(default_factory=list)

    def record_start(self, total_items: int, total_batches: int) -> None:
        """Record the start of the operation."""
        self.start_time = time.monotonic()
        self.total_items = total_items
        self.total_batches = total_batches

    def record_end(self) -> None:
        """Record the end of the operation."""
        self.end_time = time.monotonic()

    def record_batch_result(self, result: BulkBatchResult[Any, Any]) -> None:
        """Update metrics with result from a processed batch."""
        self.processed_items += len(result.items)
        self.successful_items += result.success_count
        self.failed_items += result.error_count
        self.completed_batches += 1
        self.total_retries += result.retry_count

        if result.errors:
            self.failed_batches += 1
            self.errors.extend(result.errors)

        # Update rolling average batch duration
        if self.completed_batches == 1:
            self.average_batch_time = result.duration
        else:
            self.average_batch_time = (
                (self.average_batch_time * (self.completed_batches - 1))
                + result.duration
            ) / self.completed_batches

    def record_error(self, error: Exception) -> None:
        """Record an unexpected operation-level error."""
        self.errors.append(
            BulkItemError(
                batch_id=-1,
                error="Bulk operation failed.",
                error_type=safe_error_type(error),
                retry_count=0,
                timestamp=time.monotonic(),
            ),
        )
        self.failed_batches += 1

    @property
    def duration(self) -> float | None:
        """Get the total duration of the operation."""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        if self.start_time:
            return time.monotonic() - self.start_time
        return None

    @property
    def success_rate(self) -> float:
        """Get the success rate as a percentage."""
        if self.total_items == 0:
            return 100.0
        return (self.successful_items / self.total_items) * 100.0

    @property
    def throughput(self) -> float:
        """Get items processed per second."""
        duration = self.duration
        if duration and duration > 0:
            return self.processed_items / duration
        return 0.0


@dataclass
class BulkBatchResult(Generic[T, R]):
    """Result of processing a single batch."""

    batch_id: int
    items: list[T]
    results: list[R]
    errors: list[BulkItemError]
    start_time: float
    end_time: float
    retry_count: int = 0

    @property
    def duration(self) -> float:
        """Get the duration of this batch."""
        return self.end_time - self.start_time

    @property
    def success_count(self) -> int:
        """Get the number of successful items in this batch."""
        return len(self.results)

    @property
    def error_count(self) -> int:
        """Get the number of failed items in this batch."""
        return len(self.errors)

    @property
    def is_successful(self) -> bool:
        """Check if the batch completed successfully."""
        return len(self.errors) == 0


__all__ = [
    "BulkBatchResult",
    "BulkItemError",
    "BulkOperationCancelledError",
    "BulkOperationError",
    "BulkOperationMetrics",
    "BulkOperationState",
    "BulkOperationTimeoutError",
    "R",
    "T",
]
