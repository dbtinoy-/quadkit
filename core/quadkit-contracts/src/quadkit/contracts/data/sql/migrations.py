"""Migration runner protocol.

Defines the contract for database migration execution so that ``quadkit-cli``
and other consumers can resolve a runner from the container without importing
``quadkit-sql`` directly.

Concrete implementations (Alembic adapter, ``SimpleMigrationManager``, etc.)
live in ``quadkit-sql`` and are registered by ``DatabaseProvider`` at boot time.

Example::

    from quadkit.contracts.data.sql.migrations import MigrationRunnerProtocol

    runner = await container.resolve(MigrationRunnerProtocol)
    await runner.run_migrations()
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class MigrationRunnerProtocol(Protocol):
    """Executes database migrations in the correct order.

    Implementations must be idempotent: running ``run_migrations()`` on an
    already up-to-date schema must be a no-op.  Each migration is identified
    by a unique string version identifier (e.g. ``"20240101_001"`` or the
    Alembic revision hash).

    Typical usage::

        runner = await container.resolve(MigrationRunnerProtocol)
        result = await runner.run_migrations()
        if result:
            logger.info("migrations_applied", count=len(result))
        else:
            logger.info("schema_up_to_date")
    """

    async def run_migrations(self) -> list[str]:
        """Apply all pending migrations.

        Returns:
            List of migration version identifiers that were applied.
            Empty list means the schema was already up-to-date.
        """
        ...

    async def rollback(self, target: str | None = None) -> list[str]:
        """Roll back migrations to *target*.

        Args:
            target: Version identifier to roll back to.  ``None`` rolls back
                the most recent migration only.

        Returns:
            List of migration version identifiers that were rolled back.
        """
        ...

    async def get_current_version(self) -> str | None:
        """Return the version identifier of the most recently applied migration.

        Returns:
            Version string, or ``None`` if no migrations have been applied.
        """
        ...

    async def get_pending_migrations(self) -> list[str]:
        """Return version identifiers of migrations not yet applied.

        Returns:
            Ordered list of pending migration version identifiers.
        """
        ...


__all__ = ["MigrationRunnerProtocol"]
