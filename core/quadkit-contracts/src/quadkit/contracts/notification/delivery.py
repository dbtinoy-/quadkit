"""Contracts for durable, retryable notification delivery."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol, runtime_checkable

from quadkit.contracts.mailer.types import EmailMessage
from quadkit.contracts.notification.types import DeliveryMessage


class DeliveryStatus(StrEnum):
    """States in the delivery lifecycle."""

    PENDING = "pending"
    PROCESSING = "processing"
    DELIVERED = "delivered"
    RETRYING = "retrying"
    FAILED = "failed"


@dataclass(frozen=True)
class DeliveryRecord:
    """Persisted outbox item returned to a delivery worker.

    Attributes:
        delivery_id: Stable identifier for this delivery operation.
        message: Channel-neutral payload to deliver.
        status: Current outbox state.
        attempts: Number of send attempts that have started.
        created_at: UTC timestamp at enqueue time.
        retry_after: Earliest time another attempt may start.
        last_error: Most recent transport failure, if any.
    """

    delivery_id: str
    message: DeliveryMessage
    status: DeliveryStatus
    attempts: int
    created_at: datetime
    retry_after: datetime | None = None
    last_error: str = ""


@runtime_checkable
class DeliveryStoreProtocol(Protocol):
    """Durable store contract for queued notification deliveries.

    Implementations own outbox state, attempt history, retry scheduling and
    atomic delivery leases. A worker claims a due item before sending it so
    multiple application instances do not process the same row concurrently.
    """

    async def create_pending(self, message: DeliveryMessage | EmailMessage) -> str:
        """Persist a pending delivery and return its stable identifier.

        ``EmailMessage`` remains accepted for mailer-side attempt tracking; the
        store normalizes it to a ``DeliveryMessage(channel="email")``.

        Args:
            message: Typed channel-neutral delivery or email message.

        Returns:
            Identifier for the queued delivery.
        """
        ...

    async def due_deliveries(self, limit: int = 50) -> list[DeliveryRecord]:
        """Return pending, retryable, or expired-lease deliveries in FIFO order."""
        ...

    async def get_delivery(self, delivery_id: str) -> DeliveryRecord | None:
        """Return one persisted delivery by identifier, if it exists."""
        ...

    async def claim_delivery(
        self, delivery_id: str, lease_seconds: float = 300.0
    ) -> bool:
        """Atomically lease a due delivery to one worker.

        Returns ``False`` if another worker claimed it or it is no longer due.
        """
        ...

    async def record_attempt(
        self,
        delivery_id: str,
        recipient: str,
        subject: str,
        attempt_number: int,
    ) -> None:
        """Persist an attempt row and update the delivery's attempt count."""
        ...

    async def complete_attempt(
        self,
        delivery_id: str,
        attempt_number: int,
        outcome: str,
        error: str = "",
    ) -> None:
        """Persist the outcome for a previously recorded attempt."""
        ...

    async def mark_delivered(self, delivery_id: str) -> None:
        """Mark a delivery as accepted by its channel backend."""
        ...

    async def schedule_retry(self, delivery_id: str, delay_seconds: float) -> None:
        """Set retry state and the next eligible time after a transient failure."""
        ...

    async def mark_failed(
        self,
        delivery_id: str,
        reason: str = "",
        final: bool = True,
    ) -> None:
        """Move an exhausted or permanently invalid delivery to dead-letter state."""
        ...


__all__ = ["DeliveryRecord", "DeliveryStatus", "DeliveryStoreProtocol"]
