"""Exceptions for notification delivery."""

from __future__ import annotations

from quadkit.contracts.notification.errors import NotificationError


class PermanentDeliveryFailure(NotificationError):  # noqa: N818
    """Raised when a message has exhausted all delivery retries.

    Args:
        delivery_id: The delivery record ID that failed permanently.
    """

    _code = "QK_ERR_NOTIF_015"

    def __init__(self, delivery_id: str) -> None:
        super().__init__(
            f"Permanent delivery failure for delivery_id={delivery_id}",
            channel="unknown",
            backend="unknown",
        )
        self.delivery_id = delivery_id


__all__ = ["PermanentDeliveryFailure"]
