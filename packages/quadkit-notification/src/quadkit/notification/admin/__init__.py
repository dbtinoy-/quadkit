"""Admin contributor subpackage for quadkit-notification."""

from __future__ import annotations

from quadkit.notification.admin.contributor import NotificationAdminContributor
from quadkit.notification.admin.handlers.inbox import InboxHandlers
from quadkit.notification.admin.pages.inbox import NotificationsInboxPage

__all__ = [
    "InboxHandlers",
    "NotificationAdminContributor",
    "NotificationsInboxPage",
]
