"""Inbox management page for /admin/notifications."""

from __future__ import annotations

from typing import Any

from quadkit.contracts.admin import PageContent, PaginationContent
from quadkit.contracts.admin.widget_content import (
    EmptyContent,
    TableCell,
    TableContent,
)
from quadkit.logging import get_logger
from quadkit.notification.inbox.service import InboxService

logger = get_logger(__name__)

DEFAULT_PER_PAGE = 20
MAX_PER_PAGE = 200


def _query_int(request: Any, name: str, default: int, lo: int, hi: int) -> int:
    try:
        value = int(request.query_params.get(name, default))
    except (TypeError, ValueError):
        value = default
    return max(lo, min(value, hi))


class NotificationsInboxPage:
    """Full inbox page with persisted notifications.

    Args:
        inbox_service: Inbox service. When ``None`` the default
            in-memory service is used.
    """

    def __init__(self, inbox_service: InboxService | None = None) -> None:
        self._inbox_service = inbox_service or InboxService()

    async def handle(self, request: Any) -> PageContent:
        """Handle request and return the inbox page as structured content.

        Args:
            request: The ASGI request.

        Returns:
            Structured page content for the inbox.
        """
        user = getattr(request, "user", None)
        user_id = getattr(user, "id", None) if user is not None else None

        try:
            raw_per_page = request.query_params.get(
                "per_page"
            ) or request.query_params.get("limit")
            per_page = (
                int(raw_per_page) if raw_per_page is not None else DEFAULT_PER_PAGE
            )
        except (TypeError, ValueError):
            per_page = DEFAULT_PER_PAGE
        per_page = max(1, min(per_page, MAX_PER_PAGE))
        page = _query_int(request, "page", 1, 1, 10**6)

        if user_id is None:
            messages: list[Any] = []
        else:
            try:
                messages = await self._inbox_service.get_inbox(user_id)
            except Exception as exc:  # noqa: BLE001 — non-fatal page render
                logger.warning("inbox_page.load_failed", error=str(exc))
                messages = []

        total = len(messages)
        page = min(page, max(1, (total + per_page - 1) // per_page))
        offset = (page - 1) * per_page
        page_messages = messages[offset : offset + per_page]

        if not messages:
            return PageContent(
                title="Notifications Inbox",
                body=EmptyContent(
                    title="No Notifications",
                    message="There are no notifications to display yet.",
                    icon="inbox",
                ),
            )

        rows = tuple(
            (
                TableCell(str(getattr(msg, "title", ""))),
                TableCell(str(getattr(msg, "body", ""))),
                TableCell(str(getattr(msg, "created_at", ""))),
            )
            for msg in page_messages
        )

        return PageContent(
            title="Notifications Inbox",
            body=TableContent(
                columns=("Title", "Body", "Created At"),
                rows=rows,
            ),
            pagination=PaginationContent(
                page=page,
                total=total,
                per_page=per_page,
                base_url=str(request.url).split("?")[0],
            ),
        )
