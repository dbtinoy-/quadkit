"""Active sessions widget handler."""

from __future__ import annotations

from datetime import UTC, datetime

from quadkit.contracts.admin import (
    SessionCountProtocol,
    Stat,
    StatContent,
    WidgetParams,
)
from quadkit.contracts.admin.errors import AdminError
from quadkit.contracts.auth import SessionRepositoryProtocol
from quadkit.result import Ok, Result


class ActiveSessionsWidgetHandler:
    """Handler for the active sessions widget.

    Args:
        session_repository: optional session repository. Degrades to a zero
            count when absent or when it lacks the session-count capability.
    """

    def __init__(
        self, session_repository: SessionRepositoryProtocol | None = None
    ) -> None:
        """Initialize handler with the session repository.

        Args:
            session_repository: repository implementing SessionRepositoryProtocol.
                When None, the widget reports a zero count.
        """
        self._session_repository = session_repository

    async def get_data(self, params: WidgetParams) -> Result[StatContent, AdminError]:
        """Fetch active sessions data.

        Mirrors the widget template: the count is rendered statically with
        neutral styling and the peak line is shown only when non-zero — no
        tone/threshold ladder exists in the template.

        Infrastructure failures propagate as exceptions.

        Args:
            params: Widget parameters (unused for this widget).

        Returns:
            Result containing StatContent or AdminError.
        """
        count = 0
        if isinstance(self._session_repository, SessionCountProtocol):
            cutoff = datetime.now(UTC)
            count = await self._session_repository.count_active(cutoff)
        return Ok(self._build_content(count=count, peak_today=0))

    def _build_content(self, count: int, peak_today: int) -> StatContent:
        """Build the StatContent mirroring the widget template.

        Args:
            count: Number of currently active sessions.
            peak_today: Peak session count today.

        Returns:
            StatContent with neutral styling and a conditional peak stat.
        """
        stats: list[Stat] = [
            Stat(label="Currently Active", value=str(count)),
        ]
        if peak_today > 0:
            stats.append(Stat(label="Peak today", value=str(peak_today)))
        return StatContent(stats=tuple(stats))


__all__ = ["ActiveSessionsWidgetHandler"]
