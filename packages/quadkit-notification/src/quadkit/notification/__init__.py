"""quadkit-notification — SMS, push, email, and user inbox with Named DI multi-backend support."""

from __future__ import annotations

from typing import TYPE_CHECKING

from quadkit.contracts.notification.delivery import (
    DeliveryRecord,
    DeliveryStatus,
    DeliveryStoreProtocol,
)
from quadkit.contracts.notification.errors import NotificationError
from quadkit.contracts.notification.inbox import InboxMessage, InboxStoreProtocol
from quadkit.contracts.notification.protocols import (
    DeliveryChannelProtocol,
    DeliveryDispatcherProtocol,
    PushChannelProtocol,
    SMSChannelProtocol,
)
from quadkit.contracts.notification.types import (
    DeliveryMessage,
    PushMessage,
    SMSMessage,
)
from quadkit.notification.backends.push import WebPushChannel
from quadkit.notification.config import (
    APNsDriverConfig,
    FCMDriverConfig,
    InboxConfig,
    MailerConfig,
    NamedMailerConfig,
    NamedPushConfig,
    NamedSMSConfig,
    NotificationConfig,
    SendGridDriverConfig,
    SMTPDriverConfig,
    TwilioDriverConfig,
    WebPushDriverConfig,
)
from quadkit.notification.constants import __version__
from quadkit.notification.delivery.dispatcher import NotificationDeliveryDispatcher
from quadkit.notification.delivery.mailer_channel import MailerDeliveryChannel
from quadkit.notification.delivery.retry import DeferredRetryMailer
from quadkit.notification.delivery.stores import (
    MemoryDeliveryStore,
    SqlDeliveryStore,
)
from quadkit.notification.delivery.worker import flush_retries
from quadkit.notification.events import (
    EmailBouncedEvent,
    EmailSentEvent,
    InboxMessageCreatedEvent,
    InboxMessageReadEvent,
    NotificationFailedEvent,
    NotificationSentEvent,
)
from quadkit.notification.exceptions import (
    APNsNotificationError,
    FCMNotificationError,
    InboxError,
    InboxMessageNotFoundError,
    InboxPermissionError,
    SendGridMailerError,
    SMTPMailerError,
    TwilioNotificationError,
    WebPushNotificationError,
)
from quadkit.notification.hooks import (
    NotificationFailedHook,
    NotificationSentHook,
)
from quadkit.notification.inbox.database import DatabaseInboxStore
from quadkit.notification.inbox.memory import InMemoryInboxStore
from quadkit.notification.inbox.module import InboxModule
from quadkit.notification.inbox.service import InboxService
from quadkit.notification.mailer.mailable import Mailable
from quadkit.notification.mailer.retrying_mailer import RetryingMailer
from quadkit.notification.mailer.runtime import MailerDeliveryRuntime
from quadkit.notification.mailer.sendgrid_mailer import SendGridMailer
from quadkit.notification.mailer.smtp_mailer import SMTPMailer
from quadkit.notification.module import NotificationModule
from quadkit.notification.protocols import (
    InboxStoreProtocol,
    MailerProtocol,
    PushChannelProtocol,
    SMSChannelProtocol,
)

__all__ = [
    "APNsDriverConfig",
    "APNsNotificationError",
    "DatabaseInboxStore",
    "DeferredRetryMailer",
    "DeliveryChannelProtocol",
    "DeliveryDispatcherProtocol",
    "DeliveryMessage",
    "DeliveryRecord",
    "DeliveryStatus",
    "DeliveryStoreProtocol",
    "EmailBouncedEvent",
    "EmailSentEvent",
    "FCMDriverConfig",
    "FCMNotificationError",
    "InMemoryInboxStore",
    "InboxConfig",
    "InboxError",
    "InboxMessage",
    "InboxMessageCreatedEvent",
    "InboxMessageNotFoundError",
    "InboxMessageReadEvent",
    "InboxModule",
    "InboxPermissionError",
    "InboxService",
    "InboxStoreProtocol",
    "Mailable",
    "MailerConfig",
    "MailerDeliveryChannel",
    "MailerDeliveryRuntime",
    "MailerProtocol",
    "MemoryDeliveryStore",
    "NamedMailerConfig",
    "NamedPushConfig",
    "NamedSMSConfig",
    "NotificationConfig",
    "NotificationDeliveryDispatcher",
    "NotificationError",
    "NotificationFailedEvent",
    "NotificationFailedHook",
    "NotificationModule",
    "NotificationSentEvent",
    "NotificationSentHook",
    "PushChannelProtocol",
    "PushMessage",
    "RetryingMailer",
    "SMSChannelProtocol",
    "SMSMessage",
    "SMTPDriverConfig",
    "SMTPMailer",
    "SMTPMailerError",
    "SendGridMailer",
    "SendGridMailerError",
    "SqlDeliveryStore",
    "TwilioDriverConfig",
    "TwilioNotificationError",
    "WebPushChannel",
    "WebPushDriverConfig",
    "WebPushNotificationError",
    "__version__",
    "flush_retries",
]
