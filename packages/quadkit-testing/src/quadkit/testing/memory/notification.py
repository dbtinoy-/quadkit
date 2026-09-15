"""In-memory notification channel for testing and compliance suites.

Provides :class:`InMemoryNotificationChannel`, a dependency-free channel
that records sent messages in memory and always reports healthy.  It
satisfies the send/health-check contract used by
:class:`~quadkit.testing.compliance.NotificationChannelCompliance`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from quadkit.contracts.core.health import HealthCheckResult, HealthStatus
from quadkit.contracts.mailer.types import MessageDeliveryReceipt
from quadkit.result import Ok

__all__ = ["InMemoryNotificationChannel"]


class InMemoryNotificationChannel:
    """In-memory notification channel that never fails.

    Every :meth:`send` call is recorded in :attr:`sent_messages` and
    returns an :class:`Ok` result wrapping a
    :class:`MessageDeliveryReceipt` with a unique ``message_id``.

    Example::

        channel = InMemoryNotificationChannel()
        result = await channel.send(message)
        assert result.is_ok()
        assert channel.sent_messages[0] is message
    """

    def __init__(self, channel: str = "in-memory") -> None:
        """Initialise the channel.

        Args:
            channel: Channel name reported in delivery receipts and
                health checks.
        """
        self._channel = channel
        self.sent_messages: list[Any] = []
        self.receipts: list[MessageDeliveryReceipt] = []

    @property
    def channel(self) -> str:
        """Channel name reported in delivery receipts and health checks."""
        return self._channel

    async def send(self, message: Any) -> Any:
        """Accept a notification message.

        Args:
            message: Message object to deliver (recorded, not validated).

        Returns:
            ``Ok(MessageDeliveryReceipt)`` with a non-empty
            ``message_id``.
        """
        self.sent_messages.append(message)
        receipt = MessageDeliveryReceipt(
            message_id=uuid4().hex,
            backend="memory",
            channel=self._channel,
            sent_at=datetime.now(UTC),
        )
        self.receipts.append(receipt)
        return Ok(receipt)

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Return a healthy :class:`HealthCheckResult`.

        Args:
            timeout: Ignored; present for protocol compatibility.
        """
        return HealthCheckResult(
            component=self._channel,
            status=HealthStatus.HEALTHY,
            message="in-memory channel always available",
        )
