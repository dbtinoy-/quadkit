"""Auth users management page — list registered users."""

from __future__ import annotations

from typing import Any

from quadkit.contracts.admin import PageContent
from quadkit.contracts.admin.widget_content import (
    EmptyContent,
    TableCell,
    TableContent,
)
from quadkit.contracts.auth.store import UserStoreProtocol
from quadkit.logging import get_logger

logger = get_logger(__name__)


class AuthUsersPage:
    """Admin page listing registered auth users."""

    def __init__(
        self,
        user_store: UserStoreProtocol | None = None,
    ) -> None:
        self._user_store = user_store

    async def handle(self, request: Any) -> PageContent:
        if self._user_store is None:
            return PageContent(
                title="Users",
                body=EmptyContent(
                    title="User Store Unavailable",
                    message="No user store is configured.",
                    icon="users",
                ),
            )

        try:
            users = await self._user_store.list_users()
        except Exception:
            logger.warning("auth_users.list_users_failed")
            return PageContent(
                title="Users",
                body=EmptyContent(
                    title="User Store Error",
                    message="Failed to retrieve users from the store.",
                    icon="alert-triangle",
                ),
            )

        if not users:
            return PageContent(
                title="Users",
                body=EmptyContent(
                    title="No Users Found",
                    message="There are no registered users yet.",
                    icon="users",
                ),
            )

        rows = tuple(
            (
                TableCell(str(u.user_id)),
                TableCell(str(getattr(u, "email", "-"))),
                TableCell("Active" if getattr(u, "is_active", True) else "Inactive"),
            )
            for u in users
        )

        return PageContent(
            title="Users",
            body=TableContent(columns=("ID", "Email", "Status"), rows=rows),
        )
