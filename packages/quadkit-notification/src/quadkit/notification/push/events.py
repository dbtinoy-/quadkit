"""Domain events for quadkit-notification push submodule.

Emitted when push notification operations complete. Consumed by
analytics, delivery tracking, and device management systems.
"""

from __future__ import annotations

from dataclasses import dataclass

from quadkit.contracts.domain.events import DomainEvent

__all__ = [
    "PushNotificationFailedEvent",
    "PushNotificationSentEvent",
]


@dataclass(frozen=True, init=False)
class PushNotificationSentEvent(DomainEvent):
    """Emitted when a push notification is successfully dispatched.

    Consumed by: analytics, delivery tracking.
    """

    device_token: str
    platform: str


@dataclass(frozen=True, init=False)
class PushNotificationFailedEvent(DomainEvent):
    """Emitted when a push notification dispatch fails.

    Consumed by: device management, retry logic, audit.
    """

    device_token: str
    platform: str
    reason: str
