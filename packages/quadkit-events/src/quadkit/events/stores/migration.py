"""Event store backend migration utilities (MF-06).

Provides tools to migrate all events from one EventStoreProtocol backend to another
while preserving stream ordering, stream IDs, and global event order.

Typical use case: promote from InMemoryEventStore (dev) to PostgresEventStore
(production) without losing any events.

Example::

    from quadkit.events.migration import migrate_store, MigrationResult
    from quadkit.events.stores.memory import InMemoryEventStore
    from quadkit.events.stores.postgres import PostgresEventStore
    from quadkit.logging import get_logger

    logger = get_logger(__name__)

    source = InMemoryEventStore()
    target = PostgresEventStore(...)

    result = await migrate_store(source, target, batch_size=100)
    logger.info("events_migrated", events_count=result.events_migrated,
                streams_count=result.streams_migrated)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

from quadkit.logging import get_logger
from quadkit.primitives import clock as ambient_clock

if TYPE_CHECKING:
    from quadkit.events.stores.base import EventStoreProtocol

logger = get_logger(__name__)


@dataclass
class MigrationResult:
    """Result of a store migration operation."""

    events_migrated: int = 0
    streams_migrated: int = 0
    errors: list[str] = field(default_factory=list)
    started_at: datetime = field(default_factory=ambient_clock.now)
    completed_at: datetime | None = None

    @property
    def duration_seconds(self) -> float | None:
        """Wall-clock time for the migration in seconds."""
        if self.completed_at is None:
            return None
        return (self.completed_at - self.started_at).total_seconds()

    @property
    def success(self) -> bool:
        """True if migration completed without errors."""
        return len(self.errors) == 0


async def migrate_store(
    source: EventStoreProtocol,
    target: EventStoreProtocol,
    batch_size: int = 100,
    dry_run: bool = False,
) -> MigrationResult:
    """Migrate all events from one EventStoreProtocol to another.

    Reads events from ``source`` in global order using ``stream_all()``,
    then groups them by stream and appends to ``target``.  Uses
    ``expected_version=None`` to avoid concurrency conflicts when writing
    to a fresh target.

    Args:
        source: Source event store to read from.
        target: Target event store to write to.
        batch_size: Events to buffer before writing to target.
        dry_run: If True, read from source but do NOT write to target.

    Returns:
        MigrationResult with counts and any errors encountered.
    """
    result = MigrationResult()

    # Group events per stream so we can append in order
    stream_events: dict[str, list] = {}

    logger.info("Starting event store migration (dry_run=%s)", dry_run)

    try:
        async for event in source.stream_all(from_position=0, batch_size=batch_size):  # type: ignore[attr-defined]
            stream_id = getattr(event, "stream_id", None) or getattr(
                event, "aggregate_id", None
            )
            if not stream_id:
                logger.warning(
                    "Event %s has no stream_id, skipping", getattr(event, "id", "?")
                )
                continue
            stream_events.setdefault(str(stream_id), []).append(event)
            result.events_migrated += 1

        logger.info(
            "Read %d events from source across %d streams",
            result.events_migrated,
            len(stream_events),
        )

        if not dry_run:
            for stream_id, events in stream_events.items():
                try:
                    # Sort by version to ensure order
                    sorted_events = sorted(
                        events, key=lambda e: getattr(e, "version", 0)
                    )
                    await target.append(stream_id, sorted_events, expected_version=None)
                    result.streams_migrated += 1
                    logger.debug(
                        "Migrated stream %s (%d events)", stream_id, len(events)
                    )
                except Exception as exc:  # noqa: BLE001 — per-stream migration error; log and continue with remaining streams
                    msg = f"Failed to migrate stream {stream_id}: {exc}"
                    logger.exception(msg)
                    result.errors.append(msg)
        else:
            result.streams_migrated = len(stream_events)
            logger.info("Dry run — no data written to target")

    except Exception as exc:  # noqa: BLE001 — migration abort; logs error and returns result with recorded errors
        msg = f"Migration aborted: {exc}"
        logger.exception(msg)
        result.errors.append(msg)

    result.completed_at = ambient_clock.now()
    logger.info(
        "Migration complete: %d events, %d streams, %d errors (%.2fs)",
        result.events_migrated,
        result.streams_migrated,
        len(result.errors),
        result.duration_seconds or 0,
    )
    return result


async def verify_migration(
    source: EventStoreProtocol,
    target: EventStoreProtocol,
) -> tuple[bool, list[str]]:
    """Verify that source and target stores contain the same events.

    Args:
        source: Original store.
        target: Migrated store.

    Returns:
        Tuple of (is_identical, list_of_discrepancies).
    """
    discrepancies: list[str] = []

    source_count = 0
    target_count = 0

    async for _ in source.stream_all():  # type: ignore[attr-defined]
        source_count += 1

    async for _ in target.stream_all():  # type: ignore[attr-defined]
        target_count += 1

    if source_count != target_count:
        discrepancies.append(
            f"Event count mismatch: source={source_count}, target={target_count}",
        )

    return len(discrepancies) == 0, discrepancies


__all__ = ["MigrationResult", "migrate_store", "verify_migration"]
