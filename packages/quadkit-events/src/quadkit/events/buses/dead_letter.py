"""Dead Letter Queue for the EventBusProtocol (MF-08).

When event handlers fail after all retries, the event can be sent to a
Dead Letter Store for inspection, manual replay, or alerting.

Example::

    dlq = InMemoryDeadLetterStore()
    # Wire into EventBusProtocol via config:
    #   EventBusProtocol(dead_letter_store=dlq)

    count = await dlq.get_count()
    entries = await dlq.list_entries()
    await dlq.replay(entries[0].entry_id, event_bus)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.contracts.events import EventBusProtocol

logger = get_logger(__name__)


@dataclass
class DeadLetterEntry:
    """A single entry in the dead letter queue."""

    entry_id: str = field(default_factory=lambda: str(uuid4()))
    event_type: str = ""
    event_data: dict[str, Any] = field(default_factory=dict)
    handler_name: str = ""
    error: str = ""
    failed_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    attempts: int = 0
    replayed: bool = False
    replayed_at: datetime | None = None


class DeadLetterStore:
    """Abstract interface for dead letter storage."""

    async def save(self, entry: DeadLetterEntry) -> None:
        raise NotImplementedError

    async def list_entries(
        self,
        event_type: str | None = None,
        handler_name: str | None = None,
        limit: int = 100,
    ) -> list[DeadLetterEntry]:
        raise NotImplementedError

    async def get_count(self, event_type: str | None = None) -> int:
        raise NotImplementedError

    async def mark_replayed(self, entry_id: str) -> None:
        raise NotImplementedError

    async def delete(self, entry_id: str) -> bool:
        raise NotImplementedError

    async def replay(self, entry_id: str, event_bus: EventBusProtocol) -> bool:
        """Deserialise the stored event and republish it to the bus."""
        raise NotImplementedError


class InMemoryDeadLetterStore(DeadLetterStore):
    """In-memory dead letter store for testing and single-node setups."""

    def __init__(self) -> None:
        self._entries: dict[str, DeadLetterEntry] = {}

    async def save(self, entry: DeadLetterEntry) -> None:
        self._entries[entry.entry_id] = entry
        logger.warning(
            "Dead letter: %s handler=%s error=%s",
            entry.event_type,
            entry.handler_name,
            entry.error,
        )

    async def list_entries(
        self,
        event_type: str | None = None,
        handler_name: str | None = None,
        limit: int = 100,
    ) -> list[DeadLetterEntry]:
        result = list(self._entries.values())
        if event_type:
            result = [e for e in result if e.event_type == event_type]
        if handler_name:
            result = [e for e in result if e.handler_name == handler_name]
        return result[:limit]

    async def get_count(self, event_type: str | None = None) -> int:
        entries = await self.list_entries(event_type=event_type, limit=10_000)
        return len(entries)

    async def mark_replayed(self, entry_id: str) -> None:
        if entry_id in self._entries:
            self._entries[entry_id].replayed = True
            self._entries[entry_id].replayed_at = datetime.now(UTC)

    async def delete(self, entry_id: str) -> bool:
        return self._entries.pop(entry_id, None) is not None

    async def replay(self, entry_id: str, event_bus: EventBusProtocol) -> bool:
        """Republish a dead-lettered event to the EventBusProtocol."""
        entry = self._entries.get(entry_id)
        if not entry:
            return False

        from quadkit.events.messages.event import Event

        try:
            event_data = dict(entry.event_data)
            event_data.setdefault("event_type", entry.event_type)
            event = Event(**event_data)
            await event_bus.publish(event)
            await self.mark_replayed(entry_id)
            logger.info(
                "Replayed dead letter entry %s (%s)", entry_id, entry.event_type
            )
            return True
        except Exception as e:  # noqa: BLE001 — replay failure isolation; log and return False without crashing caller
            logger.exception("Replay of %s failed", entry_id, error=str(e))
            return False

    def clear(self) -> None:
        self._entries.clear()


__all__ = [
    "DeadLetterEntry",
    "DeadLetterStore",
    "InMemoryDeadLetterStore",
]
