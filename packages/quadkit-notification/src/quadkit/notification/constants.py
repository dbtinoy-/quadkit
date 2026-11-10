"""quadkit-notification constants."""

from __future__ import annotations

import importlib.metadata

try:
    __version__: str = importlib.metadata.version("quadkit-notification")
except ImportError:
    __version__ = "0.0.0"


# ---------------------------------------------------------------------------
# Environment Variable Prefixes
# ---------------------------------------------------------------------------

ENV_PREFIX: str = "QK_NOTIFICATION__"
ENV_NESTED_DELIMITER: str = "__"

TWILIO_API_BASE: str = "https://api.twilio.com/2010-04-01"
FCM_SEND_URL: str = "https://fcm.googleapis.com/fcm/send"
DEFAULT_FCM_TIMEOUT: int = 30
DEFAULT_TWILIO_TIMEOUT: int = 30

# ---------------------------------------------------------------------------
# APNs (Apple Push Notification service)
# ---------------------------------------------------------------------------

APNS_BASE_URL: str = "https://api.push.apple.com"
APNS_SANDBOX_URL: str = "https://api.development.push.apple.com"
DEFAULT_APNS_TIMEOUT: int = 30

# === Mailer Constants (merged from mail/constants.py) ===
DEFAULT_FROM_EMAIL: str = "noreply@example.com"
DEFAULT_SMTP_PORT: int = 587
DEFAULT_SMTP_TIMEOUT: int = 30
DEFAULT_SENDGRID_TIMEOUT: int = 30
SENDGRID_API_URL: str = "https://api.sendgrid.com/v3/mail/send"

# === Inbox Constants (merged from inbox/constants.py) ===
MAX_INBOX_PAGE_SIZE: int = 100
DEFAULT_RETENTION_DAYS: int = 90

__all__ = [
    "APNS_BASE_URL",
    "APNS_SANDBOX_URL",
    "DEFAULT_APNS_TIMEOUT",
    "DEFAULT_FCM_TIMEOUT",
    "DEFAULT_FROM_EMAIL",
    "DEFAULT_RETENTION_DAYS",
    "DEFAULT_SENDGRID_TIMEOUT",
    "DEFAULT_SMTP_PORT",
    "DEFAULT_SMTP_TIMEOUT",
    "DEFAULT_TWILIO_TIMEOUT",
    "ENV_NESTED_DELIMITER",
    "ENV_PREFIX",
    "FCM_SEND_URL",
    "MAX_INBOX_PAGE_SIZE",
    "SENDGRID_API_URL",
    "TWILIO_API_BASE",
]
