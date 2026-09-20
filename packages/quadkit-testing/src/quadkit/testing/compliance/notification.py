from __future__ import annotations

"""Contract compliance suite for notification channel implementations.

Covers both :class:`~quadkit.contracts.notification.protocols.SMSChannelProtocol`
and :class:`~quadkit.contracts.notification.protocols.PushChannelProtocol`
through a shared abstract factory.  Subclass
:class:`NotificationChannelCompliance`, implement ``create_channel()`` and
``make_message()``, and pytest will run all contract checks automatically::

    class TestTwilioSMSCompliance(NotificationChannelCompliance):
        async def create_channel(self):
            return TwilioSMSChannel(config)

        async def make_message(self):
            from quadkit.contracts.notification.types import SMSMessage
            return SMSMessage(to=["+15550009999"], body="Compliance test")
"""

import abc
from typing import Any

import pytest

__all__ = ["NotificationChannelCompliance"]


class NotificationChannelCompliance(abc.ABC):
    """Compliance suite for notification channel implementations.

    Subclass and implement :meth:`create_channel` and :meth:`make_message`
    to run all compliance tests against any ``SMSChannelProtocol`` or
    ``PushChannelProtocol`` implementation.
    """

    @abc.abstractmethod
    async def create_channel(self) -> Any:
        """Create the channel implementation under test.

        Returns:
            A fresh instance implementing ``SMSChannelProtocol`` or
            ``PushChannelProtocol``.
        """
        ...

    @abc.abstractmethod
    async def make_message(self) -> Any:
        """Create an appropriate message for the channel under test.

        Returns:
            An ``SMSMessage`` or ``PushMessage`` ready for delivery.
        """
        ...

    # ------------------------------------------------------------------
    # send() contract tests
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_send_returns_ok_on_success(self) -> None:
        """send() returns an Ok result on successful acceptance."""
        channel = await self.create_channel()
        message = await self.make_message()
        result = await channel.send(message)
        assert result.is_ok(), f"Expected Ok result, got: {result}"

    @pytest.mark.asyncio
    async def test_send_returns_delivery_receipt(self) -> None:
        """send() Ok result contains a receipt with a non-empty message_id."""
        channel = await self.create_channel()
        message = await self.make_message()
        result = await channel.send(message)
        assert result.is_ok()
        receipt = result.unwrap()
        assert receipt.message_id, "MessageDeliveryReceipt.message_id must be non-empty"
        assert isinstance(receipt.message_id, str)

    # ------------------------------------------------------------------
    # health_check() contract tests
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_health_check_returns_result(self) -> None:
        """health_check() returns a HealthCheckResult instance."""
        from quadkit.contracts.core.health import HealthCheckResult

        channel = await self.create_channel()
        result = await channel.health_check()
        assert isinstance(result, HealthCheckResult)

    @pytest.mark.asyncio
    async def test_health_check_has_status(self) -> None:
        """health_check() status is HEALTHY or DEGRADED."""
        from quadkit.contracts.core.health import HealthStatus

        channel = await self.create_channel()
        result = await channel.health_check()
        assert result.status in (
            HealthStatus.HEALTHY,
            HealthStatus.DEGRADED,
        ), f"Unexpected health status: {result.status!r}"

    @pytest.mark.asyncio
    async def test_health_check_custom_timeout_accepted(self) -> None:
        """health_check() accepts an explicit timeout without raising."""
        channel = await self.create_channel()
        result = await channel.health_check(timeout=2.0)
        assert result is not None

    @pytest.mark.asyncio
    async def test_health_check_has_component_name(self) -> None:
        """health_check() result includes a non-empty component name."""
        channel = await self.create_channel()
        result = await channel.health_check()
        assert result.component, "HealthCheckResult.component must be non-empty"
        assert isinstance(result.component, str)
