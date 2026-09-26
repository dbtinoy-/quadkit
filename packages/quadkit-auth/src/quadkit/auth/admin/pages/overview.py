"""Auth overview management page — user and session counts."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from quadkit.contracts.admin import PageContent
from quadkit.contracts.admin.widget_content import Stat, StatContent
from quadkit.contracts.auth.repositories import SessionRepositoryProtocol
from quadkit.contracts.auth.store import UserStoreProtocol
from quadkit.logging import get_logger

logger = get_logger(__name__)


class AuthOverviewPage:
    """Admin overview page for authentication stats."""

    def __init__(
        self,
        user_store: UserStoreProtocol | None = None,
        session_repo: SessionRepositoryProtocol | None = None,
    ) -> None:
        self._user_store = user_store
        self._session_repo = session_repo

    async def handle(self, request: Any) -> PageContent:
        user_count: str | int = "N/A"
        session_count: str | int = "N/A"

        if self._user_store is not None:
            try:
                user_count = await self._user_store.count_users()
            except Exception:
                logger.warning("auth_overview.user_count_unavailable")

        if self._session_repo is not None:
            try:
                sessions = await self._session_repo.find_active_by_user(
                    user_id="*",
                    cutoff=datetime.now(UTC),
                )
                session_count = len(sessions)
            except Exception:
                session_count = "N/A"

        return PageContent(
            title="Authentication",
            body=StatContent(
                stats=(
                    Stat(label="Total Users", value=str(user_count), icon="users"),
                    Stat(
                        label="Active Sessions",
                        value=str(session_count),
                        icon="activity",
                    ),
                )
            ),
        )
