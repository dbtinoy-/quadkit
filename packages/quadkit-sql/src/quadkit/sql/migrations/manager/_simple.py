"""Alembic migration manager implementation.

This module provides migration management capabilities for Quadkit DB.
It supports both Alembic-based migrations (enterprise) and a simple
migration manager (community edition).

Example:
    Using AlembicManager::

        from quadkit.sql.migrations.manager import AlembicManager

        manager = AlembicManager(
            connection_or_provider="postgresql://user:pass@localhost/db",
            migrations_path="./migrations",
        )
        await manager.initialize()
        await manager.upgrade()

    Using SimpleMigrationManager::

        from quadkit.sql.migrations.manager import SimpleMigrationManager

        manager = SimpleMigrationManager(provider=db_provider)
        await manager.initialize_migration_table()
        await manager.apply_migration("001", "create_users", CREATE_USERS_SQL)
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from quadkit.contracts import (
    DatabaseProviderProtocol,
    MigrationManagerProtocol,
    MigrationRecord,
)
from quadkit.contracts.data.identifiers import Table
from quadkit.logging import get_logger
from quadkit.primitives import clock as ambient_clock
from quadkit.sql.exceptions import DatabaseError, QueryError
from quadkit.sql.migrations.engine import MigrationEngine
from quadkit.sql.migrations.introspector import SchemaIntrospector
from quadkit.sql.migrations.orchestrator import MigrationOrchestrator
from quadkit.sql.migrations.types import MigrationInfo, MigrationStatus

logger = get_logger(__name__)

Config: Any = None
ScriptDirectory: Any = None
MigrationContext: Any = None
ALEMBIC_AVAILABLE = False
try:
    from alembic.config import Config

    ALEMBIC_AVAILABLE = True
except ImportError:  # pragma: no cover - availability checked at runtime
    ALEMBIC_AVAILABLE = False

class SimpleMigrationManager(MigrationManagerProtocol):
    """Simple migration manager for community edition.

    Provides basic migration tracking and execution without advanced
    features like dependency resolution or rollback scripts.

    Example:
        Basic usage::

            manager = SimpleMigrationManager(provider=db_provider)
            await manager.initialize_migration_table()
            await manager.apply_migration("001", "create_users", CREATE_SQL)
    """

    async def create(self, name: str, message: str) -> str:
        """Create a new migration file (alias for create_migration_file).

        Args:
            name: Migration name.
            message: Migration description or SQL content.

        Returns:
            The version string of the created migration.
        """
        return await self.create_migration_file(name, f"-- {message}")

    async def get_current_version(self) -> str | None:
        """Get the version of the most recently applied migration.

        Returns:
            The version string, or None if no migrations have been applied.
        """
        applied = await self.get_applied_migrations()
        if not applied:
            return None
        return applied[-1].version

    def __init__(
        self,
        provider: DatabaseProviderProtocol | None = None,
        migrations_dir: str | None = None,
    ):
        """Initialize the simple migration manager.

        Args:
            provider: Database provider instance.
            migrations_dir: Directory for migration files. Defaults to "./migrations".
        """
        self.provider = provider
        self.migrations_dir = Path(migrations_dir or "migrations")
        self.migration_table = "__migrations"

    async def initialize_migration_table(self) -> None:
        """Initialize the migration tracking table.

        Creates the __migrations table if it doesn't exist.
        """
        if self.provider is None:
            return
        columns = {
            "version": "VARCHAR(255) PRIMARY KEY",
            "name": "VARCHAR(255) NOT NULL",
            "applied_at": "TIMESTAMP NOT NULL",
            "success": "BOOLEAN NOT NULL",
            "error_message": "TEXT",
        }

        if not await self.provider.table_exists(self.migration_table):
            await self.provider.execute(
                f"CREATE TABLE {self.migration_table} ({', '.join(f'{k} {v}' for k, v in columns.items())})",
            )

    async def get_applied_migrations(self) -> list[MigrationRecord]:
        """Get list of applied migrations.

        Returns:
            List of MigrationRecord for all applied migrations.
        """
        if self.provider is None:
            return []

        if not await self.provider.table_exists(self.migration_table):
            return []

        migration_table = Table(self.migration_table)
        result = await self.provider.execute_query(
            f"SELECT version, name, applied_at, success, error_message FROM {migration_table} ORDER BY applied_at",
        )
        return [
            MigrationRecord(
                version=row["version"],
                name=row["name"],
                applied_at=row["applied_at"],
                success=row["success"],
                error_message=row.get("error_message"),
            )
            for row in result.rows
        ]

    async def apply_migration(self, version: str, name: str, sql: str) -> bool:
        """Apply a migration to the database."""
        if self.provider is None:
            return False
        migration_table = Table(self.migration_table)
        applied_at = ambient_clock.now()

        try:
            await self.provider.execute(sql)
            await self.provider.execute(
                f"INSERT INTO {migration_table} (version, name, applied_at, success) VALUES (?, ?, ?, ?)",
                (version, name, applied_at, True),
            )
            logger.info("Applied migration %s: %s", version, name)
            return True
        except (DatabaseError, QueryError, OSError, RuntimeError) as e:
            await self.provider.execute(
                f"INSERT INTO {migration_table} (version, name, applied_at, success, error_message) VALUES (?, ?, ?, ?, ?)",
                (version, name, applied_at, False, str(e)),
            )
            logger.exception("Failed to apply migration %s", version)
            return False

    async def rollback_migration(self, version: str) -> bool:
        """Rollback a migration by removing it from the tracking table.

        Note:
            This only removes the migration record. Actual rollback
            SQL must be executed separately.

        Args:
            version: Migration version to rollback.
        """
        if self.provider is None:
            return False
        migration_table = Table(self.migration_table)
        await self.provider.execute(
            f"DELETE FROM {migration_table} WHERE version = ?",
            (version,),
        )
        logger.info("Rolled back migration %s", version)
        return True

    async def get_pending_migrations(
        self,
        available_migrations: list[str],
    ) -> list[str]:
        """Get migrations that haven't been applied yet."""
        applied = await self.get_applied_migrations()
        applied_versions = {m.version for m in applied if m.success}
        return [v for v in available_migrations if v not in applied_versions]

    async def apply_pending_migrations(self) -> list[str]:
        """Apply all pending migrations in the migrations directory."""
        if not self.migrations_dir.exists():
            return []

        applied_migrations = []
        available_versions = []
        migration_files = {}

        for file in sorted(self.migrations_dir.glob("*.sql")):
            version = file.stem
            available_versions.append(version)
            migration_files[version] = file

        pending_versions = await self.get_pending_migrations(available_versions)

        for version in pending_versions:
            file = migration_files[version]
            sql = file.read_text()

            # Try to extract name from first line comment
            name = f"Migration {version}"
            first_line = sql.splitlines()[0] if sql else ""
            if first_line.startswith("-- "):
                name = first_line[3:].strip()

            await self.apply_migration(version, name, sql)
            applied_migrations.append(version)

        return applied_migrations

    async def create_migration_file(self, name: str, sql: str) -> str:
        """Create a new migration file."""
        self.migrations_dir.mkdir(parents=True, exist_ok=True)
        now = ambient_clock.now()
        version = now.strftime("%Y%m%d%H%M%S") if now else "00000000000000"
        file_path = self.migrations_dir / f"{version}.sql"

        content = f"-- {name}\n{sql}\n"
        file_path.write_text(content)

        return version
