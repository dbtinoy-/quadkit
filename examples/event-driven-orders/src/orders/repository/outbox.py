"""Outbox for the event-driven orders demo.

A minimal in-memory transactional-outbox pattern: command handlers stage the
domain event they will publish, and the outbox tracks it until it is flushed
(here: re-published through the event bus, or reported). In a real deployment
the outbox rows live in the same transaction as the write-side state; this
demo keeps the shape of that pattern without a database.

Outbox pattern in three steps:

1. STAGE — command handler calls ``outbox.stage(event)`` after persisting.
2. TRACK — outbox records the event as ``PENDING``.
3. FLUSH — ``outbox.flush(event_bus)`` publishes all pending records and
   marks them ``SENT``.  If any publish fails, records stay ``PENDING``
   and the error is returned.

Convention: the outbox is the **single delivery path** from write side to
event bus.  Command handlers never publish directly — this prevents
double-publishing and enables at-least-once delivery guarantees.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from quadkit.contracts.events import EventBusProtocol
from quadkit.result import Err, Ok, Result


class OutboxStatus(str, Enum):
    """Lifecycle of an outbox record.

    Convention: ``str, Enum`` for string enums so members serialize
    naturally to JSON and compare equal to their string value.
    """

    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


@dataclass(frozen=True)
class OutboxRecord:
    """One staged event awaiting delivery.

    Attributes:
        event_type: Type name of the staged event.
        payload: The staged event object.
        status: Current delivery status.
    """

    event_type: str
    payload: Any
    status: OutboxStatus = OutboxStatus.PENDING


class OutboxError(Exception):
    """Raised when an outbox operation cannot be performed."""


class Outbox:
    """In-memory outbox that tracks staged domain events until flushed.

    Convention: the outbox is a simple queue — stage records in, flush
    records out.  The relay (``flush``) publishes each pending record
    through the event bus and marks it ``SENT``.

    Args:
        max_records: Cap on the number of staged records.
    """

    def __init__(self, max_records: int = 1000) -> None:
        self._records: list[OutboxRecord] = []
        self.max_records = max_records

    def stage(self, event: Any) -> None:
        """Stage an event for eventual delivery.

        Args:
            event: The event to stage.

        Raises:
            OutboxError: If no events may be staged (e.g. after max capacity).
        """
        if len(self._records) >= self.max_records:
            raise OutboxError("Outbox is full; cannot stage more events")
        self._records.append(
            OutboxRecord(event_type=type(event).__name__, payload=event)
        )

    def pending(self) -> list[OutboxRecord]:
        """Return all records that have not been delivered yet."""
        return [r for r in self._records if r.status is OutboxStatus.PENDING]

    def all(self) -> list[OutboxRecord]:
        """Return all records in staging order."""
        return list(self._records)

    async def flush(
        self,
        event_bus: EventBusProtocol,
    ) -> Result[int, OutboxError]:
        """Deliver all pending records through the event bus.

        Args:
            event_bus: The bus to publish staged events on.

        Returns:
            Ok(sent_count) when all pending records were delivered,
            Err(OutboxError) if any publish failed (records stay pending).
        """
        sent = 0
        for index, record in enumerate(self._records):
            if record.status is not OutboxStatus.PENDING:
                continue
            result = await event_bus.publish(record.payload)
            if result.is_err():
                return Err(
                    OutboxError(
                        f"Failed to publish {record.event_type}: {result.unwrap_err()}"
                    )
                )
            self._records[index] = OutboxRecord(
                event_type=record.event_type,
                payload=record.payload,
                status=OutboxStatus.SENT,
            )
            sent += 1
        return Ok(sent)


__all__ = ["Outbox", "OutboxError", "OutboxRecord", "OutboxStatus"]
