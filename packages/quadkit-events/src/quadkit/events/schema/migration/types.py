"""Migration types and data structures."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, ClassVar

from quadkit.config.base import BaseConfig
from quadkit.validation import ConfigDict, Field


class MigrationStatus(StrEnum):
    """Status of a migration job."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(init=False)
class MigrationConfig(BaseConfig):
    """Configuration for schema migration.

    Attributes:
        batch_size: Number of events to process per batch.
        parallel_workers: Number of parallel workers.
        dry_run: If True, don't actually modify events.
        stop_on_error: Stop migration on first error.
        verify_after: Verify events after migration.
        backup_before: Create backup before migration.
        timeout_seconds: Timeout for entire migration.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    batch_size: int = Field(default=1000, ge=1)
    parallel_workers: int = Field(default=4, ge=1, le=32)
    dry_run: bool = False
    stop_on_error: bool = False
    verify_after: bool = True
    backup_before: bool = True
    timeout_seconds: int | None = None


@dataclass
class MigrationResult:
    """Result of a migration operation.

    Attributes:
        migration_id: Unique migration identifier.
        status: Final status.
        started_at: When migration started.
        completed_at: When migration completed.
        total_events: Total events processed.
        total_migrated: Events actually migrated.
        total_errors: Events that failed.
        errors: List of error details.
        duration_seconds: Total duration.
    """

    migration_id: str
    status: MigrationStatus
    started_at: datetime
    completed_at: datetime | None = None
    total_events: int = 0
    total_migrated: int = 0
    total_errors: int = 0
    errors: list[dict[str, Any]] = field(default_factory=list)
    duration_seconds: float = 0.0


@dataclass
class MigrationProgress:
    """Progress of an ongoing migration.

    Attributes:
        migration_id: Migration identifier.
        status: Current status.
        total_events: Total events to process.
        processed_events: Events processed so far.
        migrated_events: Events successfully migrated.
        error_count: Number of errors.
        current_batch: Current batch number.
        total_batches: Total number of batches.
        percent_complete: Completion percentage.
    """

    migration_id: str
    status: MigrationStatus
    total_events: int
    processed_events: int
    migrated_events: int
    error_count: int
    current_batch: int
    total_batches: int

    @property
    def percent_complete(self) -> float:
        """Calculate completion percentage."""
        if self.total_events == 0:
            return 100.0
        return (self.processed_events / self.total_events) * 100


__all__ = ["MigrationConfig", "MigrationProgress", "MigrationResult", "MigrationStatus"]
