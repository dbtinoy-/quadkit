# quadkit-contracts/src/quadkit/contracts/notification/errors.py
"""Notification error types."""

from __future__ import annotations

from typing import Any

from quadkit.contracts.exceptions.domain import DomainError


class NotificationError(DomainError):
    """Base for expected, recoverable notification delivery failures.

    Attributes:
        channel: Notification channel (e.g. "sms", "push").
        backend: Name of the backend (e.g. "twilio", "fcm").
    """

    _code = "QK_ERR_NOTIF_001"

    def __init__(
        self,
        message: str = "Notification error",
        *,
        channel: str = "unknown",
        backend: str = "unknown",
        **kwargs: Any,
    ) -> None:
        details = {"backend": backend, "channel": channel, **kwargs.pop("details", {})}
        super().__init__(message, details=details, **kwargs)
        self.backend = backend
        self.channel = channel


__all__ = ["NotificationError"]
