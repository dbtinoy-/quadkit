"""Adapter that exposes SimpleMigrationManager via MigrationRunnerProtocol.

This allows CLI tools and other consumers to resolve a migration runner from
the container without depending on quadkit-sql's internal class hierarchy.
"""

from __future__ import annotations

from quadkit.contracts.data.sql.migrations import (
    MigrationRunnerProtocol,  # noqa: TC002
)
from quadkit.logging import get_logger
from quadkit.sql.migrations.manager import AlembicManager, SimpleMigrationManager

logger = get_logger(__name__)


class MigrationRunnerAdapter:
    """Wraps a migration manager to satisfy MigrationRunnerProtocol.

    Registered in DatabaseService so that any consumer can resolve
    ``MigrationRunnerProtocol`` from the container without importing
    quadkit-sql internals directly.

    Two manager flavours are supported: :class:`SimpleMigrationManager`
    (``.sql`` files in a directory) and :class:`AlembicManager` (Alembic
    revisions). ``get_pending_migrations`` detects the Alembic flavour by the
    manager's own ``introspector`` and asks it for its pending set, instead of
    passing a caller-discovered file list Alembic does not use.

    Args:
        manager: The underlying migration manager to delegate to.
    """

    # Declare protocol compliance without inheriting (structural subtyping).
    __protocol_cls__: type = MigrationRunnerProtocol  # informational only

    def __init__(self, manager: SimpleMigrationManager | AlembicManager) -> None:
        self._manager = manager

    async def run_migrations(self) -> list[str]:
        """Apply all pending migrations and return list of applied version IDs.

        Only the file-based manager applies pending migrations in bulk. The
        Alembic-backed manager exposes ``upgrade()`` instead and has no
        ``apply_pending_migrations``, so it is refused here rather than failing
        with a bare ``AttributeError`` deeper in.
        """
        await self._manager.initialize_migration_table()
        apply_pending = getattr(self._manager, "apply_pending_migrations", None)
        if apply_pending is None:
            msg = (
                "run_migrations() needs a manager that applies pending "
                "migrations in bulk; the Alembic-backed manager exposes "
                "upgrade() instead"
            )
            raise NotImplementedError(msg)
        applied: list[str] = await apply_pending()
        return applied

    async def rollback(self, target: str | None = None) -> list[str]:
        """Roll back to *target*, or roll back the most recent migration if None.

        Returns list of rolled-back version identifiers.
        """
        applied = await self._manager.get_applied_migrations()
        successful = [m for m in applied if m.success]
        if not successful:
            return []

        if target is None:
            # Roll back only the most recent migration.
            to_rollback = [successful[-1].version]
        else:
            # Roll back all migrations from the most recent down to and including target.
            versions_ordered = [m.version for m in successful]
            try:
                target_idx = versions_ordered.index(target)
            except ValueError:
                logger.warning("rollback_target_not_found", target=target)
                return []
            to_rollback = list(reversed(versions_ordered[target_idx:]))

        rolled_back: list[str] = []
        for version in to_rollback:
            if await self._manager.rollback_migration(version):
                rolled_back.append(version)
        return rolled_back

    async def get_current_version(self) -> str | None:
        """Return the version identifier of the most recently applied migration."""
        applied = await self._manager.get_applied_migrations()
        successful = [m for m in applied if m.success]
        return successful[-1].version if successful else None

    async def get_pending_migrations(self) -> list[str]:
        """Return version identifiers of not-yet-applied migrations found on disk.

        Alembic-backed managers report pending revisions from their own
        status introspection; file-based managers derive them from the
        migrations directory.
        """
        introspector = getattr(self._manager, "introspector", None)
        if introspector is not None:
            # Both supported managers (Alembic- and Simple-backed) expose
            # ``get_status`` once they carry an introspector.
            status = await self._manager.get_status()  # type: ignore[union-attr]
            return [m.revision for m in status.pending_migrations]
        migrations_dir = self._manager.migrations_dir  # type: ignore[union-attr]
        if not migrations_dir.exists():
            return []

        available = sorted(
            f.stem
            for f in migrations_dir.glob("*.sql")
            if not f.name.endswith(".down.sql")
        )
        return await self._manager.get_pending_migrations(available)


__all__ = ["MigrationRunnerAdapter"]
