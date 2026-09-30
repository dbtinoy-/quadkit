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
    MigrationRecord,
)
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


def _packaged_alembic_ini() -> Path:
    """Return the ``alembic.ini`` that sits beside the package source.

    An installed wheel carries no such file, so callers fall back to a path
    they own when this is absent.

    Returns:
        Path to the workspace ``alembic.ini`` (which need not exist).
    """
    # parents[4] lands in src/, where `command.init()` writes a template ini;
    # parents[5] is the package root that ships the real file.
    return Path(__file__).resolve().parents[5] / "alembic.ini"


class AlembicManager:
    """Alembic migration manager facade for Quadkit DB.

    Provides a high-level interface for managing database migrations using
    Alembic. Supports upgrade, downgrade, branch creation, and revision
    management.

    Example:
        Initializing and running migrations::

            manager = AlembicManager(
                connection_or_provider=db_provider,
                migrations_path="./migrations",
            )
            await manager.initialize()
            await manager.upgrade("head")
    """

    def __init__(
        self,
        connection_or_provider: Any,
        migrations_path: str | Path | None = None,
        script_location: str | Path | None = None,
        alembic_config: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the Alembic migration manager.

        Args:
            connection_or_provider: Database connection string or provider instance.
            migrations_path: Path to migrations directory. Defaults to "./migrations".
            script_location: Path to Alembic scripts. Defaults to "migrations/versions".
            alembic_config: Additional Alembic configuration options.

        Raises:
            ImportError: If Alembic is not installed.
        """
        if not ALEMBIC_AVAILABLE:
            raise ImportError("Alembic is not installed.")

        self._provider = None
        if hasattr(connection_or_provider, "url"):
            self._provider = connection_or_provider
            self.database_url = connection_or_provider.url
        else:
            self.database_url = str(connection_or_provider)
        self.connection_string = self.database_url

        self.migrations_path = Path(migrations_path or "migrations")
        self.script_location = (
            Path(script_location)
            if script_location
            else self.migrations_path / "versions"
        )
        self.alembic_config = alembic_config or {}

        # Don't create directories here, let initialize handle it
        # self.migrations_path.mkdir(parents=True, exist_ok=True)
        # Don't create script_location yet, let initialize or Alembic handle it
        # self.script_location.mkdir(parents=True, exist_ok=True)

        self.config = self._create_alembic_config()
        self.engine = MigrationEngine(self.config)
        self.introspector = SchemaIntrospector(self.config, self.connection_string)
        self.orchestrator = MigrationOrchestrator(
            self._provider,
            self.connection_string,
        )
        # Re-entrancy guard: providers boot concurrently, and lazy boot
        # triggers can double-invoke `upgrade("head")` during startup.
        self._upgraded = False

    def _create_alembic_config(self) -> Config:
        """Create and configure Alembic Config object."""
        config = Config()
        packaged_ini = _packaged_alembic_ini()
        if packaged_ini.exists():
            config.config_file_name = str(packaged_ini)
        else:
            # Installed wheel: `alembic.ini` lives at the package root, which
            # sits outside the wheel, so there is no packaged ini to reference.
            # `command.init()` asserts on `config_file_name`, so point it at
            # the directory this manager already owns; `init()` writes the
            # generated ini there, and only while that directory is empty.
            config.config_file_name = str(self.migrations_path / "alembic.ini")
        config.set_main_option("script_location", str(self.migrations_path))
        # Strip +aiosqlite/+asyncpg for Alembic which is sync
        self.connection_string = self.database_url
        if "+aiosqlite" in self.connection_string:
            self.connection_string = self.connection_string.replace("+aiosqlite", "")
        elif "+asyncpg" in self.connection_string:
            self.connection_string = self.connection_string.replace("+asyncpg", "")

        config.set_main_option("sqlalchemy.url", self.connection_string)
        config.set_main_option("version_locations", str(self.script_location))
        # `path_separator` must be set in the same breath as
        # `version_locations`: alembic >= 1.16 deprecates splitting the value
        # without it, and this manager sets `version_locations`
        # programmatically. The packaged `alembic.ini` carries
        # `path_separator = os`, so a *workspace* checkout never saw the
        # warning -- but an *installed* layout resolves without that file and
        # hit the legacy fallback on every boot. Setting it here makes the
        # two layouts behave identically instead of leaving the guarantee to a
        # file that ships only in the repo.
        config.set_main_option("path_separator", "os")
        # User overrides last, so `alembic_config={"path_separator": ":"}`
        # still wins for a project that needs the legacy character.
        for key, value in self.alembic_config.items():
            config.set_main_option(key, str(value))
        return config

    async def initialize(self) -> None:
        """Initialize the migration system.

        Creates the migration tracking table and initializes Alembic environment if needed.
        """
        await self.orchestrator.initialize_migration_table()

        # Initialize Alembic if not already done
        if (
            not self.migrations_path.exists()
            or not (self.migrations_path / "env.py").exists()
        ):
            from alembic import command
            from alembic.util.exc import CommandError

            def _init() -> Any:
                try:
                    # If directory exists but is empty, command.init is usually fine
                    # If it's not empty, it might fail.
                    command.init(self.config, str(self.migrations_path))
                except CommandError as e:
                    if "already exists and is not empty" in str(e):
                        logger.warning("Alembic init into non-empty directory: %s", e)
                        # Ensure basic files exist even if init failed due to non-empty dir
                        self.migrations_path.mkdir(parents=True, exist_ok=True)
                    else:
                        raise

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, _init)

        # Ensure versions directory exists
        self.script_location.mkdir(parents=True, exist_ok=True)

    async def upgrade(self, revision: str = "head", **kwargs: Any) -> None:
        """Run database migrations up to the specified revision.

        Concurrent invocations (e.g. providers booting in parallel) are
        collapsed into a single migration run.

        Args:
            revision: Target revision. Defaults to "head" (latest).
            **kwargs: Additional arguments passed to Alembic upgrade.
        """
        if self._upgraded:
            return
        self._upgraded = True
        await self.engine.upgrade(revision, **kwargs)

    async def downgrade(self, revision: str = "-1", **kwargs: Any) -> None:
        """Run database migrations down to the specified revision.

        Args:
            revision: Target revision. Defaults to "-1" (previous).
            **kwargs: Additional arguments passed to Alembic downgrade.
        """
        self._upgraded = False
        await self.engine.downgrade(revision, **kwargs)

    async def upgrade_dry_run(self, revision: str = "head") -> list[str]:
        """Preview migrations that would be applied without executing them.

        Args:
            revision: Target revision. Defaults to "head".

        Returns:
            List of SQL statements that would be executed.
        """
        return await self.engine.upgrade_dry_run(revision)

    async def downgrade_dry_run(self, revision: str = "base") -> list[str]:
        """Preview downgrade that would be applied without executing it.

        Args:
            revision: Target revision. Defaults to "base".

        Returns:
            List of SQL statements that would be executed.
        """
        return await self.engine.downgrade_dry_run(revision)

    async def get_status(self) -> MigrationStatus:
        """Get the current migration status.

        Returns:
            MigrationStatus with current state of migrations.
        """
        return await self.introspector.get_status()

    async def get_history(self, limit: int | None = None) -> list[MigrationInfo]:
        """Get the migration history.

        Args:
            limit: Maximum number of migrations to return. None for all.

        Returns:
            List of MigrationInfo objects representing the history.
        """
        return await self.introspector.get_history(limit)

    async def get_branches(self) -> list[dict[str, Any]]:
        """Get available Alembic branches.

        Returns:
            List of branch definitions.
        """
        return await self.introspector.get_branches()

    async def create_revision(self, message: str, **kwargs: Any) -> str:
        """Create a new database migration revision.

        Args:
            message: Revision message/description.
            **kwargs: Additional arguments for revision creation.

        Returns:
            The revision identifier.
        """
        return await self.engine.create_revision(message, **kwargs)

    async def create_initial_revision(self, message: str, **kwargs: Any) -> str:
        """Create the initial database migration revision.

        Args:
            message: Revision message/description.
            **kwargs: Additional arguments for revision creation.

        Returns:
            The revision identifier.
        """
        return await self.create_revision(message, **kwargs)

    async def create_branch(self, branch_name: str, **kwargs: Any) -> str:
        """Create a new Alembic branch.

        Args:
            branch_name: Name of the branch to create.
            **kwargs: Additional arguments.

        Returns:
            The branch revision identifier.
        """
        return await self.engine.create_branch(branch_name, **kwargs)

    async def merge_branches(self, source: str, target: str, **kwargs: Any) -> str:
        """Merge two Alembic branches.

        Args:
            source: Source branch identifier.
            target: Target branch identifier.
            **kwargs: Additional arguments.

        Returns:
            The merged revision identifier.
        """
        return await self.engine.merge_branches(source, target, **kwargs)

    async def stamp(self, revision: str) -> None:
        """Stamp the database with a specific revision without running migrations.

        Args:
            revision: Revision to stamp the database with.
        """
        await self.engine.stamp(revision)  # type: ignore[attr-defined]

    async def edit(self, revision: str) -> None:
        """Edit a revision file in the default editor.

        Args:
            revision: Revision to edit.
        """
        await self.engine.edit(revision)

    async def squash(self, revisions: list[str], message: str) -> str:
        """Squash multiple revisions into a single revision.

        Args:
            revisions: List of revision identifiers to squash.
            message: Message for the new squashed revision.

        Returns:
            The new squashed revision identifier.
        """
        return await self.engine.squash(revisions, message)

    async def validate_migrations(self) -> dict[str, Any]:
        """Validate that applied migrations match the expected state.

        Returns:
            Dictionary with validation results.
        """
        return await self.introspector.validate_migrations()

    async def get_pending_operations(self, **kwargs: Any) -> list[dict[str, Any]]:
        """Get list of pending migration operations.

        Args:
            **kwargs: Additional filtering options.

        Returns:
            List of pending operations with their details.
        """
        return await self.introspector.get_pending_operations(**kwargs)

    async def get_applied_migrations(self) -> list[MigrationRecord]:
        """Return records for all migrations applied up to the current revision.

        Note: Alembic does not natively track applied-at timestamps per
        revision.  Each returned :class:`~quadkit.contracts.MigrationRecord`
        has its ``applied_at`` set to *now* as an approximation.  For precise
        per-migration timestamps, use a custom Alembic event hook that inserts
        into a supplementary audit table.

        Returns:
            List of :class:`~quadkit.contracts.MigrationRecord` for every
            revision that has been stamped at or before the current head.
        """
        status = await self.introspector.get_status()
        if status.current_revision is None:
            return []

        history = await self.introspector.get_history()
        now = ambient_clock.now()
        applied: list[MigrationRecord] = []
        for info in history:
            applied.append(
                MigrationRecord(
                    version=info.version,
                    name=info.description or info.version,
                    applied_at=now,
                    success=True,
                    error_message=None,
                )
            )
            if info.version == status.current_revision:
                break

        return applied

    async def rollback_migration(self, version: str) -> bool:
        """Downgrade the database to *version*, effectively rolling it back.

        Args:
            version: Target Alembic revision string (e.g. ``"-1"``,
                ``"abc123"``).

        Returns:
            ``True`` if the downgrade completed successfully, ``False``
            otherwise.

        Raises:
            DatabaseError: Re-raised if the Alembic downgrade raises a hard
                database error.
        """
        try:
            await self.downgrade(version)
        except DatabaseError:
            raise
        except Exception as exc:  # noqa: BLE001 — migration framework may raise non-database exceptions; logged and returns False
            logger.error("rollback_migration_failed", version=version, error=str(exc))
            return False
        else:
            return True

    async def get_pending_migrations(
        self,
        available_migrations: list[str],
    ) -> list[str]:
        """Return the subset of *available_migrations* that have not yet been applied.

        The method intersects the caller-supplied list of revision identifiers
        with Alembic's own pending-migration set derived from the live
        database state.

        Args:
            available_migrations: Ordered list of revision identifiers the
                caller considers "available" (e.g. from a manifest or
                auto-discovery).

        Returns:
            Those identifiers from *available_migrations* that Alembic reports
            as not yet applied.
        """
        status = await self.introspector.get_status()
        pending_revisions = {m.revision for m in status.pending_migrations}
        return [v for v in available_migrations if v in pending_revisions]

    async def initialize_migration_table(self) -> None:
        """Initialize the migration tracking table."""
        await self.orchestrator.initialize_migration_table()

    async def apply_migration(self, version: str, name: str, sql: str) -> bool:
        """Apply a raw SQL migration.

        This method is primarily for compatibility and programmatic application
        of migrations. It handles session management if the provider supports it.

        Args:
            version: Migration version.
            name: Migration name.
            sql: SQL to execute.

        Returns:
            True if successful.

        Raises:
            DatabaseError: If migration fails.
        """
        from quadkit.contracts.exceptions import DatabaseError

        session_cm = None
        if hasattr(self._provider, "session"):
            session_cm = self._provider.session()  # type: ignore[union-attr]

        try:
            if session_cm:
                async with session_cm as session:
                    await session.execute(sql)
                    if hasattr(session, "commit"):
                        await session.commit()
            # Simple provider or connection string fallback
            elif hasattr(self._provider, "execute"):
                await self._provider.execute(sql)  # type: ignore[union-attr]
            else:
                # Last resort fallback to raw execution
                import aiosqlite

                if "sqlite" in str(self.connection_string):
                    path = str(self.connection_string).split("///")[-1].split("://")[-1]
                    async with aiosqlite.connect(path) as conn:
                        await conn.execute(sql)
                        await conn.commit()

            return True
        except (DatabaseError, QueryError, OSError, RuntimeError) as e:
            logger.exception("apply_migration failed")
            if session_cm:
                try:
                    # Some session CMs might not have rollback on the CM itself but on the session
                    # But the tests provide a session-like object that has rollback
                    if hasattr(session_cm, "rollback"):
                        await session_cm.rollback()
                except (DatabaseError, QueryError, OSError, RuntimeError):
                    logger.exception(
                        "Rollback failed during migration apply",
                    )
            raise DatabaseError(f"Migration apply failed: {e}") from e
