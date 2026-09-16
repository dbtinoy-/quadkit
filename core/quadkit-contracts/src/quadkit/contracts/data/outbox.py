"""Transactional outbox protocol for reliable event delivery."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from quadkit.contracts.domain.events import DomainEvent


@runtime_checkable
class OutboxStoreProtocol(Protocol):
    """Protocol for transactional outbox storage."""

    async def append_batch(self, events: list[DomainEvent]) -> None:
        """Write a batch of domain events to the outbox table atomically."""
        ...

    async def fetch_pending(self, limit: int = 100) -> list[dict[str, Any]]:
        """Fetch undelivered outbox events."""
        ...

    async def mark_delivered(self, event_id: str) -> None:
        """Mark an outbox event as successfully delivered."""
        ...

    async def mark_failed(self, event_id: str, error: str) -> None:
        """Mark an outbox event as permanently failed."""
        ...


__all__ = [
    "OutboxStoreProtocol",
]
