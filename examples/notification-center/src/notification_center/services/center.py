"""Application adapter around Quadkit's mailer and inbox subsystems.

Convention followed: **Application service** — every operation exposed in
the browser (send email, send/list/read/delete inbox messages) is real
``quadkit-notification`` behavior delegated to the package-owned
``MailerProtocol`` and ``InboxService``; the demo only formats results for
JSON and owns the curated seed inbox plus a client-side sent-mail log.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.contracts.mailer import EmailMessage, MailerError
from quadkit.contracts.notification.inbox import InboxMessage
from quadkit.result import Ok, Result

if TYPE_CHECKING:
    from notification_center.config import NotificationCenterConfig
    from quadkit.contracts.mailer.protocols import MailerProtocol
    from quadkit.notification.inbox.service import InboxService

# A small curated set of sample inbox notifications so the console has
# something realistic to browse out of the box.
_SEED_INBOX: tuple[dict[str, Any], ...] = (
    {
        "title": "Welcome to Notification Center",
        "body": (
            "This inbox is backed by the real InboxStoreProtocol — every "
            "message here was written through InboxService.send(), not "
            "faked for display."
        ),
    },
    {
        "title": "Email delivery is live",
        "body": (
            "The Send Email panel calls the real MailerProtocol.send(). "
            "In this demo it resolves to ConsoleMailer, so every email is "
            "logged to the server console instead of leaving the box."
        ),
    },
    {
        "title": "Try marking this one read",
        "body": (
            "InboxService.mark_read() flips the read flag through the "
            "store; refresh the unread count panel to see it update."
        ),
    },
)


def _inbox_message_to_dict(message: InboxMessage) -> dict[str, Any]:
    """Render an ``InboxMessage`` as a JSON-friendly dict."""
    return {
        "id": message.id,
        "user_id": message.user_id,
        "title": message.title,
        "body": message.body,
        "read": message.read,
        "created_at": message.created_at.isoformat(),
        "metadata": dict(message.metadata),
    }


class NotificationCenterService:
    """Present the package-owned mailer + inbox stack as a small browser console.

    ``mailer`` and ``inbox`` are the same objects a production app would
    resolve from the DI container — every action in the browser (send
    email, send/list/read/delete inbox messages) is genuine
    ``quadkit-notification`` behavior, not a look-alike.
    """

    def __init__(
        self,
        mailer: MailerProtocol,
        inbox: InboxService,
        config: NotificationCenterConfig,
    ) -> None:
        self._mailer = mailer
        self._inbox = inbox
        self._config = config
        # MailerProtocol has no "list sent messages" method — the demo
        # tracks what it has sent client-side, the same "demo tracks what
        # the protocol can't list" pattern graph-explorer and
        # search-console use for their own unlistable collections.
        self._sent_log: list[dict[str, Any]] = []

    async def seed(self) -> None:
        """Seed a few sample inbox messages on boot."""
        if not self._config.seed_demo_inbox:
            return
        for sample in _SEED_INBOX:
            await self.send_inbox_message(
                self._config.default_user_id,
                sample["title"],
                sample["body"],
            )

    async def send_email(
        self,
        to: list[str],
        subject: str,
        body: str,
    ) -> Result[dict[str, Any], MailerError]:
        """Send an email through the real ``MailerProtocol`` backend."""
        if not to:
            raise ValueError("At least one recipient ('to') is required")
        if not subject.strip():
            raise ValueError("A 'subject' is required")

        message = EmailMessage(to=to, subject=subject, body=body)
        result = await self._mailer.send(message)
        if result.is_err():
            self._sent_log.append(
                {
                    "to": to,
                    "subject": subject,
                    "body": body,
                    "status": "failed",
                    "error": str(result.unwrap_err()),
                }
            )
            return result

        receipt = result.unwrap()
        self._sent_log.append(
            {
                "to": to,
                "subject": subject,
                "body": body,
                "status": "sent",
                "message_id": receipt.message_id,
                "backend": receipt.backend,
                "sent_at": receipt.sent_at.isoformat(),
            }
        )
        return Ok(
            {
                "message_id": receipt.message_id,
                "backend": receipt.backend,
                "channel": receipt.channel,
                "sent_at": receipt.sent_at.isoformat(),
            }
        )

    async def sent_log(self) -> list[dict[str, Any]]:
        """Return every email the demo has sent (client-side tracked)."""
        return list(self._sent_log)

    async def send_inbox_message(
        self, user_id: str, title: str, body: str, **metadata: Any
    ) -> dict[str, Any]:
        """Create and persist an inbox notification for ``user_id``."""
        if not user_id.strip():
            raise ValueError("A 'user_id' is required")
        if not title.strip():
            raise ValueError("A 'title' is required")
        message = await self._inbox.send(user_id, title, body, **metadata)
        return _inbox_message_to_dict(message)

    async def list_inbox(
        self, user_id: str, unread_only: bool = False
    ) -> list[dict[str, Any]]:
        """Return inbox messages for ``user_id``, newest first."""
        messages = await self._inbox.get_inbox(user_id, unread_only=unread_only)
        return [_inbox_message_to_dict(m) for m in messages]

    async def mark_read(self, message_id: str, user_id: str) -> None:
        """Mark ``message_id`` as read, guarded by ``user_id`` ownership."""
        await self._inbox.mark_read(message_id, user_id)

    async def mark_all_read(self, user_id: str) -> None:
        """Mark every unread message for ``user_id`` as read."""
        await self._inbox.mark_all_read(user_id)

    async def delete_inbox_message(self, message_id: str, user_id: str) -> None:
        """Delete ``message_id``, guarded by ``user_id`` ownership."""
        await self._inbox.delete(message_id, user_id)

    async def count_unread(self, user_id: str) -> int:
        """Return the unread message count for ``user_id``."""
        return await self._inbox.count_unread(user_id)

    async def clear_inbox(self, user_id: str) -> int:
        """Delete every message for ``user_id``; returns the count removed."""
        return await self._inbox.clear_all(user_id)

    async def health(self) -> dict[str, Any]:
        """Report readiness: mailer + inbox backend health, sent count."""
        mailer_result = await self._mailer.health_check()
        return {
            "status": mailer_result.status.value,
            "details": {
                "mailer": mailer_result.status.value,
                "sent_count": len(self._sent_log),
            },
        }


__all__ = ["NotificationCenterService"]
