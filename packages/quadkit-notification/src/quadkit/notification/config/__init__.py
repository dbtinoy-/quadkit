"""Notification configuration facade.

Re-exports every public name so that
``from quadkit.notification.config import X`` continues to work unchanged.
"""

from quadkit.notification.config.inbox import InboxConfig as InboxConfig
from quadkit.notification.config.mailer import (
    MailerConfig as MailerConfig,
)
from quadkit.notification.config.mailer import (
    NamedMailerConfig as NamedMailerConfig,
)
from quadkit.notification.config.mailer import (
    SendGridDriverConfig as SendGridDriverConfig,
)
from quadkit.notification.config.mailer import (
    SMTPDriverConfig as SMTPDriverConfig,
)
from quadkit.notification.config.push import (
    APNsDriverConfig as APNsDriverConfig,
)
from quadkit.notification.config.push import (
    FCMDriverConfig as FCMDriverConfig,
)
from quadkit.notification.config.push import (
    NamedPushConfig as NamedPushConfig,
)
from quadkit.notification.config.push import (
    WebPushDriverConfig as WebPushDriverConfig,
)
from quadkit.notification.config.sms import (
    NamedSMSConfig as NamedSMSConfig,
)
from quadkit.notification.config.sms import (
    TwilioDriverConfig as TwilioDriverConfig,
)
from quadkit.notification.config.top_level import (
    NotificationConfig as NotificationConfig,
)

__all__ = [
    "APNsDriverConfig",
    "FCMDriverConfig",
    "InboxConfig",
    "MailerConfig",
    "NamedMailerConfig",
    "NamedPushConfig",
    "NamedSMSConfig",
    "NotificationConfig",
    "SMTPDriverConfig",
    "SendGridDriverConfig",
    "TwilioDriverConfig",
    "WebPushDriverConfig",
]
