"""Webhook domain types: subscriptions, events, and delivery attempts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class DeliveryStatus(str, Enum):
    """Status of a webhook delivery attempt."""

    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class WebhookSubscription:
    """A registered webhook endpoint subscription.

    Attributes:
        subscription_id: Unique identifier (UUID).
        url: HTTP(S) endpoint URL to deliver events to.
        secret: Shared secret for HMAC signature computation.
        event_types: Set of event type names to deliver. None = all events.
        active: Whether the subscription is currently active.
        description: Human-readable label for the subscription.
        tenant_id: Optional multi-tenant scoping.
        created_at: When the subscription was created.
        metadata: Arbitrary key-value context.
    """

    subscription_id: str
    url: str
    secret: str
    event_types: frozenset[str] | None = None
    active: bool = True
    description: str = ""
    tenant_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        return (
            f"WebhookSubscription(subscription_id={self.subscription_id!r}, "
            f"url={self.url!r}, secret='***', event_types={self.event_types!r}, "
            f"active={self.active!r}, description={self.description!r}, "
            f"tenant_id={self.tenant_id!r}, created_at={self.created_at!r}, "
            f"metadata={self.metadata!r})"
        )


@dataclass(frozen=True)
class WebhookEvent:
    """An event prepared for webhook delivery.

    Attributes:
        event_id: Unique identifier for deduplication (UUID).
        event_type: Dot-notation event type (e.g. "user.created").
        payload: JSON-serializable event data.
        occurred_at: When the original event occurred.
        source: Originating service or module.
    """

    event_id: str
    event_type: str
    payload: dict[str, Any]
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    source: str = ""


@dataclass(frozen=True)
class DeliveryAttempt:
    """Record of a single webhook delivery attempt.

    Attributes:
        attempt_id: Unique identifier for this attempt.
        subscription_id: Target subscription.
        event_id: The event being delivered.
        event_type: Event type name.
        status: Outcome of this attempt.
        status_code: HTTP response status code (None if connection failed).
        attempt_number: 1-based attempt counter.
        attempted_at: When this attempt was made.
        next_retry_at: Scheduled time for the next retry (None if terminal).
        error_message: Error details on failure.
        duration_ms: Round-trip time in milliseconds.
        payload: The event payload that was sent, so failed attempts can be
            redelivered with their original data (``None`` for records
            created before this field existed).
        response_body: The endpoint's response body, truncated by the sender
            (``WebhookConfig.response_body_limit``) — ``None`` when the attempt
            never reached the endpoint.
            The delivery log is the operator's only view of what the receiver
            answered; without it a failing integration shows a status code and
            nothing else.
    """

    attempt_id: str
    subscription_id: str
    event_id: str
    event_type: str
    status: DeliveryStatus
    status_code: int | None = None
    attempt_number: int = 1
    attempted_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    next_retry_at: datetime | None = None
    error_message: str | None = None
    duration_ms: float | None = None
    payload: dict[str, Any] | None = None
    response_body: str | None = None


__all__ = [
    "DeliveryAttempt",
    "DeliveryStatus",
    "WebhookEvent",
    "WebhookSubscription",
]
