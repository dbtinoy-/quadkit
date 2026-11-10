"""Convention followed: **Controller pattern** — stateless HTTP adapters;
services return ``Result[T, E]``; failures map to RFC-9457 ``ProblemDetail``.

Browser API for the focused Quadkit notification demo.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.contracts.exceptions.domain import ValidationError
from quadkit.contracts.mailer import MailerError
from quadkit.result import Err, Result
from quadkit.web import Controller, delete, get, post

if TYPE_CHECKING:
    from notification_center.services.center import NotificationCenterService


class NotificationCenterApiController(Controller):
    """Expose email sending and per-user inbox management.

    Named message routes live under ``/inbox/message/{message_id}``
    (rather than a bare ``/inbox/{message_id}``) so they never collide
    with the static ``/inbox/read-all`` or ``/inbox/unread-count``
    routes — the same "distinguishing static segment" convention
    search-console, secrets-vault, and graph-explorer use for their own
    dynamic routes.
    """

    prefix = "/api/notifications"

    def __init__(self, service: NotificationCenterService | None = None) -> None:
        self._service = service

    @get("/health")
    async def health(self) -> dict[str, Any]:
        """Return the health status of the underlying mailer backend."""
        return await self._service.health()

    @post("")
    async def send_email(
        self, payload: dict[str, Any]
    ) -> Result[dict[str, Any], MailerError]:
        """Send an email from ``{to: [...], subject, body}``.

        The request parameter is named ``payload`` (not ``body``) because
        the JSON payload itself carries an email field literally named
        ``body`` — using ``body`` for both the whole-request container and
        one of its own keys would collide during combined-model binding.
        """
        try:
            to = payload.get("to") or []
            if isinstance(to, str):
                to = [to]
            return await self._service.send_email(
                list(to), str(payload.get("subject", "")), str(payload.get("body", ""))
            )
        except ValueError as exc:
            return Err(ValidationError(str(exc)))

    @get("/sent")
    async def sent_log(self) -> dict[str, Any]:
        """List every email the demo has sent, most recent last."""
        sent = await self._service.sent_log()
        return {"count": len(sent), "sent": sent}

    @post("/inbox")
    async def send_inbox_message(
        self, payload: dict[str, Any]
    ) -> Result[dict[str, Any], ValidationError]:
        """Create an inbox notification from ``{user_id, title, body}``."""
        try:
            message = await self._service.send_inbox_message(
                str(payload.get("user_id", "")),
                str(payload.get("title", "")),
                str(payload.get("body", "")),
            )
            return {"ok": True, "message": message}
        except ValueError as exc:
            return Err(ValidationError(str(exc)))

    @get("/inbox")
    async def list_inbox(
        self, user_id: str = "", unread_only: bool = False
    ) -> dict[str, Any]:
        """List inbox messages for ``user_id``, newest first."""
        messages = await self._service.list_inbox(user_id, unread_only=unread_only)
        return {"count": len(messages), "messages": messages}

    @get("/inbox/unread-count")
    async def unread_count(self, user_id: str = "") -> dict[str, Any]:
        """Return the unread message count for ``user_id``."""
        count = await self._service.count_unread(user_id)
        return {"user_id": user_id, "unread_count": count}

    @post("/inbox/read-all")
    async def mark_all_read(self, user_id: str = "") -> dict[str, Any]:
        """Mark every unread message for ``user_id`` as read."""
        await self._service.mark_all_read(user_id)
        return {"ok": True, "user_id": user_id}

    @post("/inbox/message/{message_id}/read")
    async def mark_read(self, message_id: str, user_id: str = "") -> dict[str, Any]:
        """Mark ``message_id`` as read, guarded by ``user_id`` ownership."""
        await self._service.mark_read(message_id, user_id)
        return {"ok": True, "id": message_id}

    @delete("/inbox/message/{message_id}")
    async def delete_inbox_message(
        self, message_id: str, user_id: str = ""
    ) -> dict[str, Any]:
        """Delete ``message_id``, guarded by ``user_id`` ownership."""
        await self._service.delete_inbox_message(message_id, user_id)
        return {"ok": True, "id": message_id}

    @delete("/inbox")
    async def clear_inbox(self, user_id: str = "") -> dict[str, Any]:
        """Delete every message for ``user_id``."""
        count = await self._service.clear_inbox(user_id)
        return {"ok": True, "user_id": user_id, "deleted": count}


__all__ = ["NotificationCenterApiController"]
