"""Channel registry and dispatcher for durable notification deliveries."""

from __future__ import annotations

from collections.abc import Iterable

from quadkit.contracts.mailer import MessageDeliveryReceipt
from quadkit.contracts.notification.errors import NotificationError
from quadkit.contracts.notification.protocols import DeliveryChannelProtocol
from quadkit.contracts.notification.types import DeliveryMessage
from quadkit.result import Err, Result


class NotificationDeliveryDispatcher:
    """Route queued messages through one registered channel implementation."""

    def __init__(self, channels: Iterable[DeliveryChannelProtocol]) -> None:
        """Build an immutable channel lookup from its injected implementations.

        Args:
            channels: Concrete delivery channels, keyed by their ``channel``.

        Raises:
            ValueError: If a channel name is empty or registered twice.
        """
        channel_map: dict[str, DeliveryChannelProtocol] = {}
        for channel in channels:
            name = channel.channel.strip().lower()
            if not name:
                raise ValueError("delivery channel names must not be empty")
            if name in channel_map:
                raise ValueError(f"duplicate delivery channel: {name}")
            channel_map[name] = channel
        self._channels = channel_map

    async def send(
        self, message: DeliveryMessage
    ) -> Result[MessageDeliveryReceipt, NotificationError]:
        """Dispatch a message or return a typed unknown-channel failure."""
        channel = self._channels.get(message.channel)
        if channel is None:
            return Err(
                NotificationError(
                    f"No delivery channel is registered for {message.channel!r}",
                    channel=message.channel,
                    backend="dispatcher",
                )
            )
        return await channel.send(message)


__all__ = ["NotificationDeliveryDispatcher"]
