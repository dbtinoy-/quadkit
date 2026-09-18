"""Webhook protocols: subscription store, delivery store, delivery service."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from quadkit.contracts.webhook.types import (
        DeliveryAttempt,
        DeliveryStatus,
        WebhookEvent,
        WebhookSubscription,
    )


@runtime_checkable
class WebhookSubscriptionStoreProtocol(Protocol):
    """Storage-agnostic CRUD for webhook subscriptions."""

    async def create(self, subscription: WebhookSubscription) -> None:
        """Persist a new subscription.

        Args:
            subscription: Subscription to store.
        """
        ...

    async def get(self, subscription_id: str) -> WebhookSubscription | None:
        """Return subscription by ID, or None.

        Args:
            subscription_id: UUID to look up.

        Returns:
            The subscription if found, else None.
        """
        ...

    async def list(
        self,
        *,
        active_only: bool = True,
        event_type: str | None = None,
        tenant_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[WebhookSubscription]:
        """List subscriptions matching filters.

        Args:
            active_only: Only return active subscriptions.
            event_type: Filter to subscriptions that handle this event type.
            tenant_id: Filter by tenant.
            limit: Maximum results.
            offset: Results to skip.

        Returns:
            Filtered and paginated subscriptions.
        """
        ...

    async def update(self, subscription: WebhookSubscription) -> None:
        """Update an existing subscription.

        Args:
            subscription: Updated subscription data.
        """
        ...

    async def delete(self, subscription_id: str) -> None:
        """Remove a subscription.

        Args:
            subscription_id: UUID to remove.
        """
        ...


@runtime_checkable
class WebhookDeliveryStoreProtocol(Protocol):
    """Storage for webhook delivery attempts and dead-letter queue."""

    async def record_attempt(self, attempt: DeliveryAttempt) -> None:
        """Persist a delivery attempt record.

        Args:
            attempt: Attempt to record.
        """
        ...

    async def get_attempts(
        self,
        *,
        subscription_id: str | None = None,
        event_id: str | None = None,
        status: DeliveryStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[DeliveryAttempt]:
        """Query delivery attempts matching filters, newest-first.

        Args:
            subscription_id: Filter by subscription.
            event_id: Filter by event.
            status: Filter by delivery status.
            limit: Maximum results.
            offset: Results to skip.

        Returns:
            Matching attempts in newest-first order.
        """
        ...

    async def get_dead_letters(
        self,
        *,
        subscription_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[DeliveryAttempt]:
        """Return attempts in dead-letter status.

        Args:
            subscription_id: Optional filter by subscription.
            limit: Maximum results.
            offset: Results to skip.

        Returns:
            Dead-lettered attempts.
        """
        ...

    async def count_recent_failures(
        self,
        subscription_id: str,
        since: datetime,
    ) -> int:
        """Count failed attempts for a subscription since a given time.

        Args:
            subscription_id: Subscription to check.
            since: Count attempts after this timestamp.

        Returns:
            Count of failed attempts.
        """
        ...


@runtime_checkable
class WebhookDeliveryServiceProtocol(Protocol):
    """High-level protocol for dispatching webhook events."""

    async def dispatch(self, event: WebhookEvent) -> None:
        """Deliver an event to all matching active subscriptions.

        Args:
            event: Event to deliver.
        """
        ...

    async def redeliver(self, attempt_id: str) -> Any:
        """Redeliver a failed or dead-lettered attempt.

        Returns ``Result[None, WebhookError]``. Typed as ``Any`` because
        ``Result`` lives in ``quadkit`` (not ``quadkit-contracts``).

        Args:
            attempt_id: ID of the attempt to redeliver.

        Returns:
            Result[None, WebhookError]
        """
        ...


__all__ = [
    "WebhookDeliveryServiceProtocol",
    "WebhookDeliveryStoreProtocol",
    "WebhookSubscriptionStoreProtocol",
]
