"""quadkit-notification DI module."""

from __future__ import annotations

from quadkit.notification.di.inbox_provider import InboxProvider
from quadkit.notification.di.mailer_provider import MailerProvider
from quadkit.notification.di.provider import NotificationProvider

__all__ = ["InboxProvider", "MailerProvider", "NotificationProvider"]
