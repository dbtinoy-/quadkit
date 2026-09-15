# quadkit-contracts/src/quadkit/contracts/queue/types.py
"""Queue value types."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
import time
from typing import Any
import uuid


class DeliveryGuarantee(StrEnum):
    """Message delivery guarantees supported by queue backends.

    Attributes:
        AT_MOST_ONCE: Message may be lost but is never duplicated.
        AT_LEAST_ONCE: Message may be duplicated but is never lost.
        EXACTLY_ONCE: Message is delivered exactly once (best effort).
    """

    AT_MOST_ONCE = "at_most_once"
    AT_LEAST_ONCE = "at_least_once"
    EXACTLY_ONCE = "exactly_once"


@dataclass(frozen=True)
class BusMessage:
    """A message transported through the queue backend.

    ``id`` defaults to a new UUID4.  ``timestamp`` defaults to the current
    wall-clock time.  Both are set via field defaults so callers do not need
    to supply them.

    Attributes:
        id: Unique message identifier.
        topic: Destination topic or queue name.
        payload: Arbitrary message body; must be serialisable by the backend.
        headers: Opaque string key-value headers passed to the broker.
        timestamp: Unix epoch timestamp when the message was created.
        ttl: Time-to-live in seconds; ``None`` uses the backend default.
        priority: Message priority (higher = more urgent); backend-dependent.
        delivery_guarantee: Delivery semantics for this message.
        retry_count: Number of times this message has been retried.
        max_retries: Maximum retries before routing to DLQ.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    topic: str = ""
    payload: Any = None
    headers: dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    ttl: float | None = None
    priority: int = 0
    delivery_guarantee: DeliveryGuarantee = DeliveryGuarantee.AT_LEAST_ONCE
    retry_count: int = 0
    max_retries: int = 3

    def is_expired(self) -> bool:
        """Return ``True`` if the message TTL has elapsed."""
        if self.ttl is None:
            return False
        return time.time() > self.timestamp + self.ttl

    def should_retry(self) -> bool:
        """Return ``True`` if the message may be retried."""
        return self.retry_count < self.max_retries and not self.is_expired()


__all__ = ["BusMessage", "DeliveryGuarantee"]
