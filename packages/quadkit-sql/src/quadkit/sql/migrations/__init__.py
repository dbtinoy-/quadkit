"""Migrations package exports for Quadkit DB"""
from __future__ import annotations

# Re-export public API from submodules
from quadkit.sql.migrations.base import (
    Migration,
    MigrationDependencyError,
    MigrationError,
    MigrationExecutionError,
    MigrationNotFoundError,
    MigrationRecord,
    MigrationValidationError,
    PythonMigration,
    SQLMigration,
)
from quadkit.sql.migrations.generator import (
    ColumnDefinition,
    MigrationGenerator,
    ModelAnalyzer,
    SchemaDiff,
    TableDefinition,
)
from quadkit.sql.migrations.manager import AlembicManager
from quadkit.sql.migrations.types import MigrationInfo, MigrationStatus

__all__ = [
    "AlembicManager",
    "ColumnDefinition",
    "Migration",
    "MigrationDependencyError",
    "MigrationError",
    "MigrationExecutionError",
    "MigrationGenerator",
    "MigrationInfo",
    "MigrationNotFoundError",
    "MigrationRecord",
    "MigrationStatus",
    "MigrationValidationError",
    "ModelAnalyzer",
    "PythonMigration",
    "SQLMigration",
    "SchemaDiff",
    "TableDefinition",
    "create_migration",
    "get_pending_migrations",
    "init_migrations",
    "migrate_down",
    "migrate_up",
]

# Re-export public API from submodules
from quadkit.sql.migrations.api import (
    create_migration,
    create_migration_branch,
    get_migration_branches,
    get_pending_migrations,
    init_migrations,
    merge_migration_branches,
    migrate_down,
    migrate_down_dry_run,
    migrate_up,
    migrate_up_dry_run,
    rollback_dry_run,
    rollback_migrations,
    rollback_to_revision,
    validate_migrations,
)

# Convenience wrappers have been moved to the `api` module.
