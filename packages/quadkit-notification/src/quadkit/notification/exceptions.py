"""quadkit-notification leaf exceptions."""

from __future__ import annotations

from typing import Any

from quadkit.contracts.exceptions.domain import DomainError
from quadkit.contracts.mailer.errors import MailerError
from quadkit.contracts.notification.errors import NotificationError


class TwilioNotificationError(NotificationError):
    """Twilio SMS delivery failure."""

    _code = "QK_ERR_NOTIF_003"

    def __init__(
        self,
        message: str = "Twilio SMS error",
        *,
        twilio_code: int | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, channel="sms", backend="twilio", **kwargs)
        self.twilio_code = twilio_code


class FCMNotificationError(NotificationError):
    """FCM push notification delivery failure."""

    _code = "QK_ERR_NOTIF_004"

    def __init__(
        self,
        message: str = "FCM push error",
        *,
        fcm_error: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, channel="push", backend="fcm", **kwargs)
        self.fcm_error = fcm_error


class APNsNotificationError(NotificationError):
    """APNs push notification delivery failure."""

    _code = "QK_ERR_NOTIF_005"

    def __init__(
        self,
        message: str = "APNs push error",
        *,
        apns_reason: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, channel="push", backend="apns", **kwargs)
        self.apns_reason = apns_reason


class WebPushNotificationError(NotificationError):
    """Web Push notification delivery failure."""

    _code = "QK_ERR_NOTIF_011"

    def __init__(
        self,
        message: str = "Web Push error",
        *,
        status_code: int = 0,
        reason: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, channel="push", backend="web_push", **kwargs)
        self.status_code = status_code
        self.reason = reason


# === Mail Exceptions (merged from mail/exceptions.py) ===


class SMTPMailerError(MailerError):
    """SMTP-specific delivery failure (rejection, auth error, etc.)."""

    _code = "QK_ERR_NOTIF_006"

    def __init__(
        self,
        message: str = "SMTP delivery error",
        *,
        smtp_code: int | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, backend="smtp", **kwargs)
        self.smtp_code = smtp_code


class SendGridMailerError(MailerError):
    """SendGrid API delivery failure."""

    _code = "QK_ERR_NOTIF_007"

    def __init__(
        self,
        message: str = "SendGrid delivery error",
        *,
        status_code: int | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, backend="sendgrid", **kwargs)
        self.status_code = status_code


# === Inbox Exceptions (merged from inbox/exceptions.py) ===


class InboxError(DomainError):
    """Base exception for all inbox submodule errors."""

    _code: str = "QK_ERR_NOTIF_008"


class InboxMessageNotFoundError(InboxError):
    """Raised when a requested inbox message does not exist."""

    _code: str = "QK_ERR_NOTIF_009"


class InboxPermissionError(InboxError):
    """Raised when a user attempts to access another user's inbox messages."""

    _code: str = "QK_ERR_NOTIF_010"


__all__ = [
    "APNsNotificationError",
    "FCMNotificationError",
    "InboxError",
    "InboxMessageNotFoundError",
    "InboxPermissionError",
    "SMTPMailerError",
    "SendGridMailerError",
    "TwilioNotificationError",
    "WebPushNotificationError",
]
