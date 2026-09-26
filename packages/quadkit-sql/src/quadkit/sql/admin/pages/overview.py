from __future__ import annotations

from typing import Any

from quadkit.contracts.admin import PageContent, Tone
from quadkit.contracts.admin.widget_content import EmptyContent, Stat, StatContent
from quadkit.contracts.data.sql.database import (
    DatabaseProviderProtocol,
    MigrationManagerProtocol,
)
from quadkit.logging import get_logger

logger = get_logger(__name__)


class SqlOverviewPage:
    def __init__(
        self,
        db: DatabaseProviderProtocol | None = None,
        migration_manager: MigrationManagerProtocol | None = None,
    ) -> None:
        self._db = db
        self._migration_manager = migration_manager

    async def handle(self, request: Any) -> PageContent:
        if self._db is None:
            return PageContent(
                title="SQL Database",
                body=EmptyContent(
                    title="Database Unavailable",
                    message="The database provider could not be resolved.",
                    icon="database",
                ),
            )
        connected = False
        migration_count = 0
        try:
            async with self._db.scoped_context():
                connected = True
        except Exception:
            connected = False

        if self._migration_manager is not None:
            try:
                migrations = await self._migration_manager.get_applied_migrations()
                migration_count = len(migrations)
            except Exception:
                migration_count = 0

        return PageContent(
            title="SQL Database",
            body=StatContent(
                stats=(
                    Stat(
                        label="DB Status",
                        value="Connected" if connected else "Disconnected",
                        icon="database",
                        delta="OK" if connected else "DOWN",
                        tone=Tone.SUCCESS if connected else Tone.DANGER,
                    ),
                    Stat(
                        label="Migrations",
                        value=str(migration_count),
                        icon="arrow-up-circle",
                    ),
                )
            ),
        )
