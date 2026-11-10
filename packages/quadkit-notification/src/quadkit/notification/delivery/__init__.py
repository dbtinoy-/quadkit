"""Notification delivery retry queue module.

The deferred-retry half of email delivery: a wrapper that schedules re-sends
rather than sleeping in-process, the delivery-state stores it records through,
and the worker that executes what it scheduled. The in-process wrapper lives in
:mod:`quadkit.notification.mailer.retrying_mailer`.
"""

from __future__ import annotations

from quadkit.notification.delivery.dispatcher import NotificationDeliveryDispatcher
from quadkit.notification.delivery.exceptions import PermanentDeliveryFailure
from quadkit.notification.delivery.inbox_channel import InboxDeliveryChannel
from quadkit.notification.delivery.mailer_channel import MailerDeliveryChannel
from quadkit.notification.delivery.retry import DeferredRetryMailer
from quadkit.notification.delivery.stores import MemoryDeliveryStore, SqlDeliveryStore
from quadkit.notification.delivery.worker import flush_retries

__all__ = [
    "DeferredRetryMailer",
    "InboxDeliveryChannel",
    "MailerDeliveryChannel",
    "MemoryDeliveryStore",
    "NotificationDeliveryDispatcher",
    "PermanentDeliveryFailure",
    "SqlDeliveryStore",
    "flush_retries",
]
