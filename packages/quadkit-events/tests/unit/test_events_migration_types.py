"""Tests for events migration types."""

from datetime import datetime, timezone

import pytest

from quadkit.events.schema.migration.types import (
    MigrationConfig,
    MigrationProgress,
    MigrationResult,
    MigrationStatus,
)


class TestMigrationStatus:
    """Tests for MigrationStatus enum."""

    def test_migration_status_values(self) -> None:
        """Test MigrationStatus enum values."""
        assert MigrationStatus.PENDING.value == "pending"
        assert MigrationStatus.RUNNING.value == "running"
        assert MigrationStatus.COMPLETED.value == "completed"
        assert MigrationStatus.FAILED.value == "failed"
        assert MigrationStatus.CANCELLED.value == "cancelled"

    def test_migration_status_members(self) -> None:
        """Test MigrationStatus has expected members."""
        members = list(MigrationStatus)
        assert len(members) == 5


class TestMigrationConfig:
    """Tests for MigrationConfig."""

    def test_migration_config_defaults(self) -> None:
        """Test MigrationConfig default values."""
        config = MigrationConfig()
        assert config.batch_size == 1000
        assert config.parallel_workers == 4
        assert config.dry_run is False
        assert config.stop_on_error is False
        assert config.verify_after is True
        assert config.backup_before is True

    def test_migration_config_with_values(self) -> None:
        """Test MigrationConfig with custom values."""
        config = MigrationConfig(
            batch_size=500,
            parallel_workers=8,
            dry_run=True,
            timeout_seconds=3600,
        )
        assert config.batch_size == 500
        assert config.parallel_workers == 8
        assert config.dry_run is True
        assert config.timeout_seconds == 3600


class TestMigrationResult:
    """Tests for MigrationResult."""

    def test_migration_result_creation(self) -> None:
        """Test creating MigrationResult."""
        now = datetime.now(timezone.utc)
        result = MigrationResult(
            migration_id="mig-123",
            status=MigrationStatus.COMPLETED,
            started_at=now,
            completed_at=now,
            total_events=1000,
            total_migrated=1000,
            total_errors=0,
        )
        assert result.migration_id == "mig-123"
        assert result.status == MigrationStatus.COMPLETED
        assert result.total_events == 1000

    def test_migration_result_with_errors(self) -> None:
        """Test MigrationResult with errors."""
        result = MigrationResult(
            migration_id="mig-456",
            status=MigrationStatus.FAILED,
            started_at=datetime.now(timezone.utc),
            total_events=1000,
            total_migrated=900,
            total_errors=100,
            errors=[{"event_id": "1", "error": "Parse error"}],
        )
        assert result.status == MigrationStatus.FAILED
        assert result.total_errors == 100
        assert len(result.errors) == 1


class TestMigrationProgress:
    """Tests for MigrationProgress."""

    def test_migration_progress_creation(self) -> None:
        """Test creating MigrationProgress."""
        progress = MigrationProgress(
            migration_id="mig-789",
            status=MigrationStatus.RUNNING,
            total_events=1000,
            processed_events=500,
            migrated_events=450,
            error_count=50,
            current_batch=5,
            total_batches=10,
        )
        assert progress.migration_id == "mig-789"
        assert progress.status == MigrationStatus.RUNNING
        assert progress.processed_events == 500

    def test_migration_progress_percent_complete(self) -> None:
        """Test percent_complete calculation."""
        progress = MigrationProgress(
            migration_id="mig-789",
            status=MigrationStatus.RUNNING,
            total_events=1000,
            processed_events=500,
            migrated_events=450,
            error_count=50,
            current_batch=5,
            total_batches=10,
        )
        assert progress.percent_complete == 50.0

    def test_migration_progress_zero_events(self) -> None:
        """Test percent_complete with zero events."""
        progress = MigrationProgress(
            migration_id="mig-789",
            status=MigrationStatus.COMPLETED,
            total_events=0,
            processed_events=0,
            migrated_events=0,
            error_count=0,
            current_batch=0,
            total_batches=0,
        )
        assert progress.percent_complete == 100.0