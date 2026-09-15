"""DeliveryStoreProtocol — contract for persistent notification delivery tracking."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Protocol, runtime_checkable


class DeliveryStatus(StrEnum):
    """States in the delivery lifecycle."""

    PENDING = "pending"
    DELIVERED = "delivered"
    RETRYING = "retrying"
    FAILED = "failed"


@runtime_checkable
class DeliveryStoreProtocol(Protocol):
    """Protocol for persisting notification delivery attempts.

    Implementations record each send attempt and its outcome so that
    delivery history is preserved for auditing, alerting, and dead-letter
    inspection. A single delivery operation may generate multiple attempt
    records when retry logic is in play.
    """

    async def record_attempt(
        self,
        delivery_id: str,
        recipient: str,
        subject: str,
        attempt_number: int,
    ) -> None:
        """Record a delivery attempt.

        Args:
            delivery_id: Stable identifier for the overall delivery operation.
            recipient: Comma-separated list of recipient addresses.
            subject: Message subject line.
            attempt_number: 1-based attempt counter within this delivery.
        """
        ...

    async def create_pending(self, message: Any) -> str:
        """Record a new pending delivery and return its delivery_id.

        Args:
            message: The message being sent.

        Returns:
            A unique delivery_id string for tracking this delivery.
        """
        ...

    async def mark_delivered(self, delivery_id: str) -> None:
        """Mark a delivery as successfully delivered.

        Args:
            delivery_id: Identifier for the delivery operation.
        """
        ...

    async def get_retry_count(self, delivery_id: str) -> int:
        """Return the number of delivery attempts made so far.

        Args:
            delivery_id: Identifier for the delivery operation.

        Returns:
            Current attempt count.
        """
        ...

    async def increment_retry(self, delivery_id: str) -> int:
        """Increment the attempt counter and return the new value.

        Args:
            delivery_id: Identifier for the delivery operation.

        Returns:
            New attempt count after incrementing.
        """
        ...

    async def schedule_retry(self, delivery_id: str, delay_seconds: float) -> None:
        """Schedule a retry after ``delay_seconds``.

        Args:
            delivery_id: Identifier for the delivery operation.
            delay_seconds: Seconds to wait before retrying.
        """
        ...

    async def mark_failed(
        self,
        delivery_id: str,
        reason: str = "",
        final: bool = True,
    ) -> None:
        """Mark a delivery attempt as failed.

        Args:
            delivery_id: Identifier for the delivery operation.
            reason: Human-readable failure description.
            final: ``True`` when all retry attempts are exhausted and no further
                sends will be attempted. ``False`` for intermediate failures
                where retry is still pending.
        """
        ...


__all__ = ["DeliveryStatus", "DeliveryStoreProtocol"]
