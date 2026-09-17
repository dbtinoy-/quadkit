"""Outbox pattern implementation for reliable event publishing.

Provides an in-memory Outbox for testing and local development.
For production with database persistence, use the OutboxEventStore
from the the optional provider extension.

The Outbox pattern ensures events are stored in the same transaction
as business data, then relayed asynchronously for publishing.

Example::

    from quadkit.memory import InMemoryOutbox, OutboxRelay
    from quadkit.memory import InMemoryEventBus

    # Create components
    event_bus = InMemoryEventBus()
    outbox = InMemoryOutbox()
    relay = OutboxRelay(outbox, event_bus)

    # In your service (same transaction as business data)
    async with uow:
        user = User(id="123", name="Alice")
        uow.register_new(user)
        outbox.store_event(UserCreated(user_id=user.user_id))
        await uow.commit()

    # Relay processes events asynchronously
    await relay.process_pending()
"""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import uuid4

from quadkit.contracts.domain.events import DomainEvent
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from quadkit.contracts.events import EventBusProtocol

logger = get_logger(__name__)


class OutboxStatus(StrEnum):
    """Status of an outbox entry."""

    PENDING = "pending"
    PUBLISHED = "published"
    FAILED = "failed"


@dataclass
class OutboxEntry:
    """A single entry in the outbox.

    Attributes:
        entry_id: Unique identifier for this entry
        event: The domain event to be published
        status: Current status of the entry
        created_at: When the entry was created
        published_at: When the entry was published (if applicable)
        error: Error message if publishing failed
    """

    entry_id: str = field(default_factory=lambda: str(uuid4()))
    event: DomainEvent = field(default_factory=DomainEvent)
    status: OutboxStatus = OutboxStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    published_at: datetime | None = None
    error: str | None = None


class InMemoryOutbox:
    """In-memory Outbox implementation for testing and local development.

    Stores events in memory and provides methods for the relay to
    retrieve and process them. Not suitable for production use
    (events are lost on process restart).

    Example::

        outbox = InMemoryOutbox()

        # Store event (typically in same transaction as business data)
        outbox.store_event(UserCreated(user_id="123"))

        # Retrieve pending events for processing
        pending = outbox.get_pending()

        # Mark as published after successful publish
        outbox.mark_published(entry.entry_id)
    """

    def __init__(self) -> None:
        """Initialize an empty in-memory outbox."""
        self._entries: dict[str, OutboxEntry] = {}
        self._pending_ids: deque[str] = deque()
        self._lock = asyncio.Lock()

    async def store_event(self, event: DomainEvent) -> OutboxEntry:
        """Store a domain event in the outbox.

        Args:
            event: The domain event to store

        Returns:
            The created outbox entry
        """
        async with self._lock:
            entry = OutboxEntry(event=event)
            self._entries[entry.entry_id] = entry
            self._pending_ids.append(entry.entry_id)
            logger.debug(
                "outbox_event_stored",
                entry_id=entry.entry_id,
                event_type=type(event).__name__,
            )
            return entry

    async def get_pending(self, limit: int = 100) -> list[OutboxEntry]:
        """Retrieve pending entries for processing.

        Args:
            limit: Maximum number of entries to retrieve

        Returns:
            List of pending outbox entries
        """
        async with self._lock:
            result = []
            for _ in range(min(limit, len(self._pending_ids))):
                if not self._pending_ids:
                    break
                entry_id = self._pending_ids.popleft()
                entry = self._entries.get(entry_id)
                if entry and entry.status == OutboxStatus.PENDING:
                    result.append(entry)
                else:
                    # Put it back if not pending (shouldn't happen)
                    self._pending_ids.append(entry_id)
            return result

    async def mark_published(self, entry_id: str) -> None:
        """Mark an entry as successfully published.

        Args:
            entry_id: The ID of the entry to mark
        """
        async with self._lock:
            entry = self._entries.get(entry_id)
            if entry:
                entry.status = OutboxStatus.PUBLISHED
                entry.published_at = datetime.now(UTC)
                logger.debug("outbox_entry_published", entry_id=entry_id)

    async def mark_failed(self, entry_id: str, error: str) -> None:
        """Mark an entry as failed.

        Args:
            entry_id: The ID of the entry to mark
            error: The error message
        """
        async with self._lock:
            entry = self._entries.get(entry_id)
            if entry:
                entry.status = OutboxStatus.FAILED
                entry.error = error
                logger.warning("outbox_entry_failed", entry_id=entry_id, error=error)

    async def retry_failed(self) -> list[OutboxEntry]:
        """Retry failed entries by marking them as pending again.

        Returns:
            List of entries that were queued for retry
        """
        async with self._lock:
            retried = []
            for entry in self._entries.values():
                if entry.status == OutboxStatus.FAILED:
                    entry.status = OutboxStatus.PENDING
                    entry.error = None
                    # Guard against double-enqueue: the entry may still be
                    # queued from before it failed, and a duplicate id in the
                    # pending queue would cause the relay to publish it twice.
                    if entry.entry_id not in self._pending_ids:
                        self._pending_ids.append(entry.entry_id)
                    retried.append(entry)
            logger.info("outbox_retry_queued", count=len(retried))
            return retried

    def get_stats(self) -> dict[str, int]:
        """Get statistics about the outbox.

        Returns:
            Dictionary with counts by status
        """
        stats = {"pending": 0, "published": 0, "failed": 0}
        for entry in self._entries.values():
            stats[entry.status.value] += 1
        return stats

    async def clear_published(self, older_than: datetime | None = None) -> int:
        """Remove published entries to free memory.

        Args:
            older_than: Only remove entries published before this time

        Returns:
            Number of entries removed
        """
        async with self._lock:
            to_remove = []
            for entry_id, entry in self._entries.items():
                if entry.status == OutboxStatus.PUBLISHED:
                    if older_than is None or (
                        entry.published_at and entry.published_at < older_than
                    ):
                        to_remove.append(entry_id)

            for entry_id in to_remove:
                del self._entries[entry_id]

            logger.debug("outbox_cleared_published", count=len(to_remove))
            return len(to_remove)


class OutboxRelay:
    """Relays events from the Outbox to the EventBusProtocol.

    Processes pending outbox entries and publishes them to the
    configured event bus. Handles failures and retries.

    Example::

        relay = OutboxRelay(outbox, event_bus)

        # Process all pending events
        await relay.process_pending()

        # Or run continuously in background
        task = asyncio.create_task(relay.run_relay_loop())
    """

    def __init__(
        self,
        outbox: InMemoryOutbox,
        event_bus: EventBusProtocol,
        *,
        batch_size: int = 100,
        on_publish_error: Callable[[OutboxEntry, Exception], Awaitable[None]]
        | None = None,
    ) -> None:
        """Initialize the relay.

        Args:
            outbox: The outbox to read events from
            event_bus: The event bus to publish to
            batch_size: Number of events to process in one batch
            on_publish_error: Optional callback for publish errors
        """
        self.outbox = outbox
        self.event_bus = event_bus
        self.batch_size = batch_size
        self.on_publish_error = on_publish_error
        self._running = False

    async def process_pending(self) -> tuple[int, int]:
        """Process all pending events in the outbox.

        Returns:
            Tuple of (published_count, failed_count)
        """
        entries = await self.outbox.get_pending(limit=self.batch_size)
        published = 0
        failed = 0

        for entry in entries:
            try:
                await self._publish_entry(entry)
                published += 1
            except Exception as exc:
                failed += 1
                await self.outbox.mark_failed(entry.entry_id, str(exc))
                if self.on_publish_error:
                    await self.on_publish_error(entry, exc)
                logger.exception("outbox_publish_failed", entry_id=entry.entry_id)

        logger.debug("outbox_batch_processed", published=published, failed=failed)
        return published, failed

    async def _publish_entry(self, entry: OutboxEntry) -> None:
        """Publish a single outbox entry."""
        await self.event_bus.publish(entry.event)
        await self.outbox.mark_published(entry.entry_id)
        logger.debug(
            "outbox_event_published",
            entry_id=entry.entry_id,
            event_type=type(entry.event).__name__,
        )

    async def run_relay_loop(
        self,
        poll_interval: float = 1.0,
        max_consecutive_errors: int = 10,
    ) -> None:
        """Run a continuous relay loop.

        This method runs indefinitely until stop_relay() is called.
        It polls the outbox for pending events and processes them.

        Args:
            poll_interval: Seconds between polls when no events
            max_consecutive_errors: Max errors before backing off
        """
        self._running = True
        consecutive_errors = 0

        logger.info("outbox_relay_started")

        while self._running:
            try:
                published, failed = await self.process_pending()

                if published > 0 or failed > 0:
                    consecutive_errors = 0 if published > 0 else consecutive_errors + 1
                else:
                    # No events to process, wait before polling again
                    await asyncio.sleep(poll_interval)

                if consecutive_errors >= max_consecutive_errors:
                    logger.error(
                        "outbox_relay_too_many_errors", consecutive=consecutive_errors
                    )
                    await asyncio.sleep(poll_interval * 5)
                    consecutive_errors = 0

            except Exception as e:
                logger.exception("outbox_relay_error", error=str(e))
                consecutive_errors += 1
                await asyncio.sleep(poll_interval * min(consecutive_errors, 10))

        logger.info("outbox_relay_stopped")

    def stop_relay(self) -> None:
        """Signal the relay loop to stop."""
        self._running = False


__all__ = [
    "InMemoryOutbox",
    "OutboxEntry",
    "OutboxRelay",
    "OutboxStatus",
]
