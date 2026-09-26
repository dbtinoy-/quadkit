from __future__ import annotations

from typing import Any

from quadkit.contracts.admin import PageContent
from quadkit.contracts.admin.widget_content import (
    EmptyContent,
    TableCell,
    TableContent,
)
from quadkit.contracts.data.sql.database import MigrationManagerProtocol
from quadkit.logging import get_logger

logger = get_logger(__name__)


class SqlMigrationsPage:
    def __init__(
        self,
        migration_manager: MigrationManagerProtocol | None = None,
    ) -> None:
        self._migration_manager = migration_manager

    async def handle(self, request: Any) -> PageContent:
        if self._migration_manager is None:
            return PageContent(
                title="Migrations",
                body=EmptyContent(
                    title="Migrations Unavailable",
                    message="No migration manager is configured for this database.",
                    icon="arrow-up-circle",
                ),
            )

        try:
            migrations = await self._migration_manager.get_applied_migrations()
        except Exception:
            return PageContent(
                title="Migrations",
                body=EmptyContent(
                    title="Error",
                    message="Failed to load migrations. Check the server logs for details.",
                    icon="alert-triangle",
                ),
            )

        if not migrations:
            return PageContent(
                title="Migrations",
                body=EmptyContent(
                    title="No Migrations",
                    message="No migrations have been applied yet.",
                    icon="arrow-up-circle",
                ),
            )

        rows = tuple(
            (
                TableCell(str(m.version)),
                TableCell(str(m.name)),
                TableCell("Applied" if m.success else "Failed"),
                TableCell(m.applied_at.isoformat() if m.applied_at else ""),
            )
            for m in migrations
        )

        return PageContent(
            title="Migrations",
            body=TableContent(
                columns=("Version", "Name", "Status", "Applied At"),
                rows=rows,
            ),
        )
