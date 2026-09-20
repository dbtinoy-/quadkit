"""Migration registry for database migrations.

This module provides a registry pattern for managing database migrations.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
import re
from typing import Any, ClassVar

from quadkit.contracts.data.sql.database import DatabaseProviderProtocol


@dataclass
class Migration:
    """Represents a database migration."""

    version: str
    name: str
    filename: str
    applied_at: datetime | None = None
    success: bool = True


@dataclass
class MigrationPlan:
    """Plan for migration operations."""

    to_apply: list[Migration] = field(default_factory=list)
    to_rollback: list[Migration] = field(default_factory=list)


class MigrationBackend(abc.ABC):
    """Abstract base class for migration backends."""

    name: ClassVar[str]

    @abc.abstractmethod
    async def get_applied_migrations(self) -> list[Migration]:
        """Get list of applied migrations."""

    @abc.abstractmethod
    async def apply_migration(self, migration: Migration) -> bool:
        """Apply a migration."""

    @abc.abstractmethod
    async def rollback_migration(self, migration: Migration) -> bool:
        """Rollback a migration."""

    @abc.abstractmethod
    async def create_migration(self, name: str) -> str:
        """Create a new migration file."""


class SQLMigrationBackend(MigrationBackend):
    """SQL-based migration backend."""

    name = "sql"

    def __init__(
        self,
        provider: DatabaseProviderProtocol,
        migrations_dir: Path | str = "migrations",
    ) -> None:
        self.provider = provider
        self.migrations_dir = Path(migrations_dir)
        self.migrations_dir.mkdir(parents=True, exist_ok=True)

    async def get_applied_migrations(self) -> list[Migration]:
        try:
            result = await self.provider.execute_query(
                "SELECT version, name, applied_at, success FROM schema_migrations ORDER BY version",
            )
            migrations = []
            for row in result.rows:
                migrations.append(
                    Migration(
                        version=row["version"],
                        name=row["name"],
                        filename=f"{row['version']}_{row['name']}.sql",
                        applied_at=row.get("applied_at"),
                        success=row.get("success", True),
                    ),
                )
            return migrations
        except Exception:  # noqa: BLE001 — migration listing degrades to empty
            return []

    async def apply_migration(self, migration: Migration) -> bool:
        migration_file = self.migrations_dir / migration.filename
        if not migration_file.exists():
            return False

        try:
            sql = migration_file.read_text()
            await self.provider.execute(sql)

            await self.provider.execute(
                "INSERT INTO schema_migrations (version, name, applied_at, success) VALUES (?, ?, ?, ?)",
                (
                    migration.version,
                    migration.name,
                    datetime.now(UTC).isoformat(),
                    True,
                ),
            )
            return True
        except Exception:  # noqa: BLE001 — migration check degrades to False
            return False

    async def rollback_migration(self, migration: Migration) -> bool:
        rollback_file = self.migrations_dir / migration.filename.replace(
            ".sql",
            ".down.sql",
        )
        if not rollback_file.exists():
            return False

        try:
            sql = rollback_file.read_text()
            await self.provider.execute(sql)

            await self.provider.execute(
                "DELETE FROM schema_migrations WHERE version = ?",
                (migration.version,),
            )
            return True
        except Exception:  # noqa: BLE001 — migration check degrades to False
            return False

    async def create_migration(self, name: str) -> str:
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        version = f"{timestamp}_{name.replace(' ', '_').lower()}"
        filename = f"{version}.sql"
        filepath = self.migrations_dir / filename

        content = f"""-- Migration: {name}
-- Version: {version}
-- Created: {datetime.now(UTC).isoformat()}

-- Write your SQL migration here

"""
        filepath.write_text(content)

        rollback_filepath = self.migrations_dir / filename.replace(".sql", ".down.sql")
        rollback_content = f"""-- Rollback for migration: {name}

-- Write your rollback SQL here

"""
        rollback_filepath.write_text(rollback_content)

        return version


class MigrationRegistry:
    """Registry for migration backends.

    This registry ships no built-in backends — populate it explicitly with
    :meth:`register` (e.g. from ``create_migration_manager``).
    """

    def __init__(self) -> None:
        self._backends: dict[str, MigrationBackend] = {}

    def register(self, name: str, backend: MigrationBackend) -> None:
        """Register a migration backend."""
        self._backends[name] = backend

    def get(self, name: str) -> MigrationBackend | None:
        """Get a backend by name."""
        return self._backends.get(name)

    def get_all(self) -> dict[str, MigrationBackend]:
        """Get all registered backends."""
        return self._backends.copy()


class MigrationManager:
    """Manages migration operations."""

    def __init__(self, backend: MigrationBackend):
        self.backend = backend

    async def get_status(self) -> dict[str, Any]:
        """Get migration status."""
        applied = await self.backend.get_applied_migrations()

        available = []
        migrations_dir = getattr(self.backend, "migrations_dir", None)
        if migrations_dir and migrations_dir.exists():
            for f in migrations_dir.glob("*.sql"):
                if not f.name.endswith(".down.sql"):
                    match = re.match(r"^(\d+_\d+_)", f.stem)
                    if match:
                        available.append(f.stem)

        applied_versions = {m.version for m in applied}
        pending = [v for v in available if v not in applied_versions]

        return {
            "applied": [m.version for m in applied],
            "pending": pending,
            "total_applied": len(applied),
            "total_pending": len(pending),
        }

    async def migrate_up(self, target_version: str | None = None) -> MigrationPlan:
        """Apply pending migrations."""
        applied = await self.backend.get_applied_migrations()
        applied_versions = {m.version for m in applied}

        migrations_dir = getattr(self.backend, "migrations_dir", None)
        if not migrations_dir:
            return MigrationPlan()

        to_apply = []
        for f in sorted(migrations_dir.glob("*.sql")):
            if f.name.endswith(".down.sql"):
                continue

            match = re.match(r"^(\d+_\d+_)", f.stem)
            if match and f.stem not in applied_versions:
                name = f.stem[len(match.group(1)) :]
                to_apply.append(
                    Migration(
                        version=f.stem,
                        name=name,
                        filename=f.name,
                    ),
                )
                if target_version and f.stem == target_version:
                    break

        plan = MigrationPlan(to_apply=to_apply)

        for migration in to_apply:
            success = await self.backend.apply_migration(migration)
            if not success:
                break

        return plan

    async def migrate_down(self, steps: int = 1) -> MigrationPlan:
        """Rollback migrations."""
        applied = await self.backend.get_applied_migrations()
        if not applied:
            return MigrationPlan()

        to_rollback = applied[-steps:] if steps else applied
        plan = MigrationPlan(to_rollback=list(to_rollback))

        for migration in reversed(to_rollback):
            success = await self.backend.rollback_migration(migration)
            if not success:
                break

        return plan

    async def create_migration(self, name: str) -> str:
        """Create a new migration."""
        return await self.backend.create_migration(name)

    async def reset(self) -> bool:
        """Reset the database (drop all tables)."""
        return False


def create_migration_manager(
    provider: Any,
    backend_name: str = "sql",
    migrations_dir: str = "migrations",
) -> MigrationManager:
    """Factory function to create a migration manager."""
    if backend_name == "sql":
        backend = SQLMigrationBackend(provider, migrations_dir)
    else:
        raise ValueError(f"Unknown migration backend: {backend_name}. Available: sql")

    MigrationRegistry().register(backend_name, backend)
    return MigrationManager(backend)


__all__ = [
    "Migration",
    "MigrationBackend",
    "MigrationManager",
    "MigrationPlan",
    "MigrationRegistry",
    "SQLMigrationBackend",
    "create_migration_manager",
]
