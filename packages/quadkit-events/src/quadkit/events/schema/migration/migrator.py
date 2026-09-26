"""Schema migration functionality."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from quadkit.events.messages.event import Event
from quadkit.events.schema.evolution import SchemaEvolution
from quadkit.events.schema.migration.types import (
    MigrationConfig,
    MigrationProgress,
    MigrationResult,
    MigrationStatus,
)
from quadkit.logging import get_logger

logger = get_logger(__name__)


class SchemaMigrator:
    """Migrate event schemas to newer versions.

    This class handles the migration of event schemas from older versions
    to newer versions using the schema evolution system.

    Example:
        ```python
        migrator = SchemaMigrator(event_store, evolution)

        # Migrate specific events
        result = await migrator.migrate_events(
            event_type="UserCreated",
            target_version=3,
        )

        # Migrate all events
        result = await migrator.migrate_all_events()
        ```
    """

    def __init__(
        self,
        event_store: Any,
        evolution: SchemaEvolution,
        config: MigrationConfig | None = None,
    ) -> None:
        """Initialize schema migrator.

        Args:
            event_store: Event store instance.
            evolution: Schema evolution instance.
            config: Migration configuration.
        """
        self.event_store = event_store
        self.evolution = evolution
        self.config = config or MigrationConfig()
        self._cancelled = False
        self._current_migration: MigrationProgress | None = None

    async def migrate_events(
        self,
        event_type: str,
        target_version: int,
        aggregate_ids: list[str] | None = None,
    ) -> MigrationResult:
        """Migrate events of a specific type to target version.

        Args:
            event_type: Type of events to migrate.
            target_version: Target schema version.
            aggregate_ids: Optional aggregate IDs to filter by.

        Returns:
            Migration result.
        """
        migration_id = str(uuid4())
        started_at = datetime.now(UTC)

        result = MigrationResult(
            migration_id=migration_id,
            status=MigrationStatus.RUNNING,
            started_at=started_at,
        )

        try:
            # Get events to migrate
            events = await self._get_events_for_type(event_type, aggregate_ids)
            result.total_events = len(events)

            # Process events
            for event in events:
                if self._cancelled:
                    result.status = MigrationStatus.CANCELLED
                    break

                try:
                    current_version = getattr(event, "schema_version", 1)
                    if current_version < target_version:
                        if not self.config.dry_run:
                            migrated = await self.evolution.migrate_event(
                                event,
                                target_version,
                            )
                            await self._update_event(event, migrated)
                        result.total_migrated += 1
                except (RuntimeError, ValueError, TypeError, AttributeError) as e:
                    result.total_errors += 1
                    result.errors.append(
                        {
                            "event_id": getattr(event, "event_id", "unknown"),
                            "error": str(e),
                        },
                    )
                    if self.config.stop_on_error:
                        result.status = MigrationStatus.FAILED
                        break

            if result.status == MigrationStatus.RUNNING:
                result.status = MigrationStatus.COMPLETED

        except Exception as e:  # noqa: BLE001 — migration catch-all; records failure status and continues
            result.status = MigrationStatus.FAILED
            result.errors.append({"error": str(e)})
            logger.exception("Migration failed")

        result.completed_at = datetime.now(UTC)
        result.duration_seconds = (
            result.completed_at - result.started_at
        ).total_seconds()

        return result

    async def migrate_all_events(
        self,
        version_map: dict[str, int] | None = None,
    ) -> MigrationResult:
        """Migrate all events to target versions.

        Args:
            version_map: Optional mapping of event type to target version.
                        If None, migrates to latest versions.

        Returns:
            Migration result.
        """
        migration_id = str(uuid4())
        started_at = datetime.now(UTC)

        result = MigrationResult(
            migration_id=migration_id,
            status=MigrationStatus.RUNNING,
            started_at=started_at,
        )

        try:
            # Get all events
            events = await self._get_all_events()
            result.total_events = len(events)

            # Build version map if not provided
            if version_map is None:
                version_map = await self._build_version_map(events)

            # Process in batches
            for batch in self._batch_events(events):
                if self._cancelled:
                    result.status = MigrationStatus.CANCELLED
                    break

                batch_results = await self._process_batch(batch, version_map)
                result.total_migrated += batch_results["migrated"]
                result.total_errors += batch_results["errors"]
                result.errors.extend(batch_results["error_details"])

                if self.config.stop_on_error and batch_results["errors"] > 0:
                    result.status = MigrationStatus.FAILED
                    break

            if result.status == MigrationStatus.RUNNING:
                result.status = MigrationStatus.COMPLETED

        except Exception as e:  # noqa: BLE001 — migration catch-all; records failure status and continues
            result.status = MigrationStatus.FAILED
            result.errors.append({"error": str(e)})
            logger.exception("Migration failed")

        result.completed_at = datetime.now(UTC)
        result.duration_seconds = (
            result.completed_at - result.started_at
        ).total_seconds()

        return result

    async def migrate_with_progress(
        self,
        version_map: dict[str, int] | None = None,
    ) -> AsyncIterator[MigrationProgress]:
        """Migrate events with progress updates.

        Args:
            version_map: Optional mapping of event type to target version.

        Yields:
            Migration progress updates.
        """
        migration_id = str(uuid4())

        events = await self._get_all_events()
        total_events = len(events)
        batches = list(self._batch_events(events))
        total_batches = len(batches)

        if version_map is None:
            version_map = await self._build_version_map(events)

        progress = MigrationProgress(
            migration_id=migration_id,
            status=MigrationStatus.RUNNING,
            total_events=total_events,
            processed_events=0,
            migrated_events=0,
            error_count=0,
            current_batch=0,
            total_batches=total_batches,
        )

        self._current_migration = progress
        yield progress

        for i, batch in enumerate(batches):
            if self._cancelled:
                progress.status = MigrationStatus.CANCELLED
                yield progress
                break

            batch_results = await self._process_batch(batch, version_map)

            progress.current_batch = i + 1
            progress.processed_events += len(batch)
            progress.migrated_events += batch_results["migrated"]
            progress.error_count += batch_results["errors"]

            yield progress

        if progress.status == MigrationStatus.RUNNING:
            progress.status = MigrationStatus.COMPLETED
            yield progress

        self._current_migration = None

    def cancel(self) -> None:
        """Cancel the current migration."""
        self._cancelled = True

    async def verify_migration(
        self,
        result: MigrationResult,
        version_map: dict[str, int],
    ) -> dict[str, Any]:
        """Verify a completed migration.

        Args:
            result: Migration result to verify.
            version_map: Expected version map.

        Returns:
            Verification report.
        """
        report: dict[str, Any] = {
            "migration_id": result.migration_id,
            "verified": True,
            "issues": [],
        }

        events = await self._get_all_events()

        for event in events:
            event_type = type(event).__name__
            expected_version = version_map.get(event_type)
            current_version = getattr(event, "schema_version", 1)

            if expected_version and current_version != expected_version:
                report["verified"] = False
                report["issues"].append(
                    {
                        "event_id": getattr(event, "event_id", "unknown"),
                        "event_type": event_type,
                        "expected_version": expected_version,
                        "actual_version": current_version,
                    },
                )

        return report

    async def _get_events_for_type(
        self,
        event_type: str,
        aggregate_ids: list[str] | None,
    ) -> list[Event]:
        """Get events for a specific type."""
        all_events = await self._get_all_events()
        filtered = list(filter(lambda e: type(e).__name__ == event_type, all_events))

        if aggregate_ids:
            filtered = [
                e for e in filtered if getattr(e, "aggregate_id", None) in aggregate_ids
            ]

        return filtered

    async def _get_all_events(self) -> list[Event]:
        """Get all events from the store."""
        # This depends on the event store implementation
        # Most stores have a method to iterate all events
        from typing import cast

        if hasattr(self.event_store, "get_all_events"):
            return cast("list[Event]", await self.event_store.get_all_events())
        if hasattr(self.event_store, "stream_all"):
            events = []
            async for event in self.event_store.stream_all():
                events.append(event)
            return events
        # Fallback: can't get all events
        logger.warning("Event store doesn't support getting all events")
        return []

    async def _update_event(
        self,
        old_event: Event,
        new_event: Event,
    ) -> None:
        """Update an event in the store."""
        if hasattr(self.event_store, "update_event"):
            await self.event_store.update_event(old_event, new_event)
        else:
            logger.warning("Event store doesn't support updating events")

    async def _build_version_map(
        self,
        events: list[Event],
    ) -> dict[str, int]:
        """Build version map from events."""
        version_map: dict[str, int] = {}

        for event in events:
            event_type = type(event).__name__
            if event_type not in version_map:
                latest = await self.evolution.registry.get_latest_version(event_type)
                if latest:
                    version_map[event_type] = latest

        return version_map

    def _batch_events(
        self,
        events: list[Event],
    ) -> list[list[Event]]:
        """Split events into batches."""
        return [
            events[i : i + self.config.batch_size]
            for i in range(0, len(events), self.config.batch_size)
        ]

    async def _process_batch(
        self,
        batch: list[Event],
        version_map: dict[str, int],
    ) -> dict[str, Any]:
        """Process a batch of events."""
        migrated = 0
        errors = 0
        error_details: list[dict[str, Any]] = []

        for event in batch:
            try:
                event_type = type(event).__name__
                target_version = version_map.get(event_type)

                if target_version:
                    current_version = getattr(event, "schema_version", 1)
                    if current_version < target_version:
                        if not self.config.dry_run:
                            new_event = await self.evolution.migrate_event(
                                event,
                                target_version,
                            )
                            await self._update_event(event, new_event)
                        migrated += 1
            except (RuntimeError, ValueError, TypeError, AttributeError) as e:
                errors += 1
                error_details.append(
                    {
                        "event_id": getattr(event, "event_id", "unknown"),
                        "error": str(e),
                    },
                )

        return {"migrated": migrated, "errors": errors, "error_details": error_details}


__all__ = ["SchemaMigrator"]
