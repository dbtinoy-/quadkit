"""Migration status widget handler."""

from __future__ import annotations

from quadkit.contracts.admin import Stat, StatContent, Tone, WidgetParams
from quadkit.contracts.admin.errors import AdminError
from quadkit.contracts.data import MigrationManagerProtocol
from quadkit.contracts.data.sql.migrations import MigrationRunnerProtocol
from quadkit.result import Ok, Result


class MigrationStatusWidgetHandler:
    """Fetches migration status.

    Args:
        migration_manager: injected MigrationManagerProtocol.
        migration_runner: optional MigrationRunnerProtocol used to compute
            pending migrations from disk; omitted when unavailable.
    """

    def __init__(
        self,
        migration_manager: MigrationManagerProtocol | None = None,
        migration_runner: MigrationRunnerProtocol | None = None,
    ) -> None:
        """Initialize the handler.

        Args:
            migration_manager: Migration manager protocol.
            migration_runner: Migration runner protocol, or None when no
                runner is available (pending reports zero).
        """
        self._migration_manager = migration_manager
        self._migration_runner = migration_runner

    async def get_data(self, params: WidgetParams) -> Result[StatContent, AdminError]:
        """Fetch migration status.

        Reports applied and pending migration counts; a fully migrated
        state renders as success, otherwise a warning.

        Args:
            params: Widget parameters.

        Returns:
            Result with StatContent or AdminError.
        """
        if self._migration_manager is None:
            return Ok(
                StatContent(
                    stats=(
                        Stat(label="Applied", value="Unavailable", tone=Tone.WARNING),
                        Stat(label="Pending", value="Unavailable", tone=Tone.WARNING),
                    )
                )
            )
        applied = await self._migration_manager.get_applied_migrations()
        if self._migration_runner is not None:
            pending = await self._migration_runner.get_pending_migrations()
        else:
            pending = []
        return Ok(
            StatContent(
                stats=(
                    Stat(label="Applied", value=f"{len(applied)} applied"),
                    Stat(
                        label="Pending",
                        value=f"{len(pending)} pending",
                        tone=Tone.SUCCESS if not pending else Tone.WARNING,
                    ),
                )
            )
        )


__all__ = ["MigrationStatusWidgetHandler"]
