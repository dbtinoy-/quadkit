"""Auth sessions management page — active session listing."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from quadkit.contracts.admin import PageContent
from quadkit.contracts.admin.widget_content import (
    EmptyContent,
    TableCell,
    TableContent,
)
from quadkit.contracts.auth.repositories import SessionRepositoryProtocol
from quadkit.logging import get_logger

logger = get_logger(__name__)


class AuthSessionsPage:
    """Admin page listing active authentication sessions."""

    def __init__(
        self,
        session_repo: SessionRepositoryProtocol | None = None,
    ) -> None:
        self._session_repo = session_repo

    async def handle(self, request: Any) -> PageContent:
        if self._session_repo is None:
            return PageContent(
                title="Sessions",
                body=EmptyContent(
                    title="Session Repository Unavailable",
                    message="No session repository is configured.",
                    icon="activity",
                ),
            )

        try:
            sessions = await self._session_repo.find_active_by_user(
                user_id="*",
                cutoff=datetime.now(UTC),
            )
        except Exception:
            logger.warning("auth_sessions.list_failed")
            return PageContent(
                title="Sessions",
                body=EmptyContent(
                    title="Error",
                    message="Failed to retrieve sessions.",
                    icon="alert-triangle",
                ),
            )

        if not sessions:
            return PageContent(
                title="Sessions",
                body=EmptyContent(
                    title="No Active Sessions",
                    message="There are no active sessions.",
                    icon="activity",
                ),
            )

        rows = tuple(
            (
                TableCell(str(s.get("session_id", "-"))),
                TableCell(str(s.get("user_id", "-"))),
                TableCell("Active"),
                TableCell(str(s.get("expires_at", ""))),
            )
            for s in sessions
        )

        return PageContent(
            title="Sessions",
            body=TableContent(
                columns=("Session ID", "User ID", "Status", "Expires"),
                rows=rows,
            ),
        )
