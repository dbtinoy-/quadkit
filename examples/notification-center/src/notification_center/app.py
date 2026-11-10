"""Convention followed: **Composition root** — one file knows how modules,
providers and controllers fit; ``create_app(config=...)`` is the injection
seam.

Composition root for the Notification Center demo.

This is a single-package niche demo: ``MailerModule`` owns email delivery
(``MailerProtocol``, defaulting to a console-logging backend) and
``InboxProvider`` owns per-user inbox persistence (``InboxService``) — both
are ``quadkit-notification`` package objects, not look-alikes. The
application layer only presents those package-owned APIs in a small
notification console: send an email, browse a user's inbox, mark
messages read, and clear them out.
"""

from __future__ import annotations

from notification_center.controllers.api import NotificationCenterApiController
from notification_center.di.provider import NotificationCenterProvider
from notification_center.ui.pages import NotificationCenterPageController
from quadkit.app.base import Application
from quadkit.config.main import QuadkitConfig
from quadkit.di.provider import Provider
from quadkit.notification.config import InboxConfig
from quadkit.notification.di.inbox_provider import InboxProvider
from quadkit.notification.mailer.module import MailerModule
from quadkit.web.module import WebModule


def build_modules() -> list[object]:
    """Build the Quadkit modules required by the notification center demo.

    ``MailerModule.configure()`` is called with no arguments: with no
    backends configured and ``console_fallback`` defaulting to ``True``,
    it binds a real ``ConsoleMailer`` — every sent email is logged to the
    server console instead of contacting SMTP/SendGrid, keeping the demo
    dependency-free while still exercising the real ``MailerProtocol``
    send path.
    """
    return [
        MailerModule.configure(),
        WebModule.configure(
            controllers=[
                NotificationCenterApiController,
                NotificationCenterPageController,
            ],
        ),
    ]


def build_providers() -> list[Provider]:
    """Build the DI providers for the notification center demo.

    ``InboxProvider`` is added directly (not via a Module) because
    ``quadkit-notification`` has no combined module bundling mailer and
    inbox together — this mirrors how ``examples/audit-trail`` adds
    ``DatabaseModule``/``AuditModule`` as siblings.  ``store_backend="memory"``
    keeps the inbox dependency-free, matching how ``search-console`` picks
    SQLite over a networked backend.
    """
    return [
        InboxProvider(config=InboxConfig(store_backend="memory")),
        NotificationCenterProvider(),
    ]


def create_app(config: QuadkitConfig | None = None) -> Application:
    """Create and configure the notification center application."""
    app = Application(name="notification-center", config=config)
    app.add_modules(build_modules())
    app.add_providers(build_providers())
    return app


__all__ = ["build_modules", "build_providers", "create_app"]
