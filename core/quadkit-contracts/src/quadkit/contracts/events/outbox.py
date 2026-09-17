"""Outbox pattern protocols for reliable event publishing.

Defines the contracts that both in-memory (core) and database-backed
(the optional provider / quadkit-messaging) outbox implementations must satisfy.

The Outbox pattern stores domain events in the same transaction as
business data, then relays them asynchronously to the event bus,
guaranteeing at-least-once delivery.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

__all__ = [
    "OutboxBackendProtocol",
    "OutboxEntryProtocol",
    "OutboxRelayProtocol",
    "OutboxStatus",
]


class OutboxStatus(StrEnum):
    """Lifecycle status of an outbox entry."""

    PENDING = "pending"
    PUBLISHED = "published"
    FAILED = "failed"


@runtime_checkable
class OutboxEntryProtocol(Protocol):
    """Protocol describing a single persisted outbox entry.

    Concrete implementations may be dataclasses, ORM models, or plain
    dicts — anything that exposes these attributes satisfies the protocol.
    """

    @property
    def entry_id(self) -> str:
        """Unique identifier for this outbox entry."""
        ...

    @property
    def event(self) -> Any:
        """The domain event payload to be published."""
        ...

    @property
    def status(self) -> OutboxStatus:
        """Current lifecycle status of the entry."""
        ...

    @property
    def error(self) -> str | None:
        """Error message from the last failed publish attempt, if any."""
        ...


@runtime_checkable
class OutboxBackendProtocol(Protocol):
    """Protocol for the outbox store — write side of the outbox pattern.

    Implementations are responsible for persisting entries and updating
    their status. In production this maps to a database table; in tests
    an in-memory deque suffices.

    Note: For SQL-backed outbox storage, use
    ``quadkit.contracts.data.outbox.OutboxStoreProtocol``.
    """

    async def store_event(self, event: Any) -> OutboxEntryProtocol:
        """Persist a domain event as a new PENDING outbox entry.

        Args:
            event: Domain event to store.

        Returns:
            The newly created outbox entry.
        """
        ...

    async def get_pending(self, *, limit: int = 100) -> list[OutboxEntryProtocol]:
        """Retrieve up to *limit* entries with PENDING status.

        Args:
            limit: Maximum number of entries to return.

        Returns:
            List of pending outbox entries, oldest first.
        """
        ...

    async def mark_published(self, entry_id: str) -> None:
        """Mark an entry as successfully PUBLISHED.

        Args:
            entry_id: Identifier of the entry to update.
        """
        ...

    async def mark_failed(self, entry_id: str, error: str) -> None:
        """Mark an entry as FAILED and record the error message.

        Args:
            entry_id: Identifier of the entry to update.
            error: Human-readable description of the failure.
        """
        ...


@runtime_checkable
class OutboxRelayProtocol(Protocol):
    """Protocol for the outbox relay — read/dispatch side of the pattern.

    The relay polls the store for pending entries and publishes them to
    the event bus, updating entry status after each attempt.
    """

    async def process_pending(self) -> tuple[int, int]:
        """Process all currently pending outbox entries.

        Returns:
            Tuple of ``(published_count, failed_count)``.
        """
        ...
