"""Migration record and manager protocol."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class MigrationRecord:
    """Record of a database migration."""

    version: str
    name: str
    applied_at: datetime
    success: bool
    error_message: str | None


@runtime_checkable
class MigrationManagerProtocol(Protocol):
    """Protocol for migration management."""

    async def initialize_migration_table(self) -> None:
        """Initialize the migration tracking table."""
        ...

    async def get_applied_migrations(self) -> list[MigrationRecord]:
        """Get list of applied migrations."""
        ...

    async def apply_migration(self, version: str, name: str, sql: str) -> bool:
        """Apply a migration."""
        ...

    async def rollback_migration(self, version: str) -> bool:
        """Rollback a migration."""
        ...

    async def get_pending_migrations(
        self,
        available_migrations: list[str],
    ) -> list[str]:
        """Get migrations that haven't been applied yet."""
        ...


# ---------------------------------------------------------------------------
# Focused sub-protocols (D1.2)
#
# Code that only needs one concern should depend on the narrowest protocol:
#
#   - TransactionManagerProtocol  — begin / commit / rollback only
#   - SchemaManagerProtocol       — DDL / table inspection
#   - CrudOperationsProtocol      — raw query execution
#   - HealthMonitorProtocol       — health-check only
#
# DatabaseProviderProtocol satisfies all four.
# ---------------------------------------------------------------------------
