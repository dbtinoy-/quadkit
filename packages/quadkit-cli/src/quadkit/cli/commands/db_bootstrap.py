"""Bootstrap helpers shared by the database management commands."""

from __future__ import annotations

import importlib
from typing import Any

import typer

from quadkit.cli.output import OutputManager
from quadkit.cli.package_names import module_for


async def _bootstrap_migration_runner() -> tuple[Any, Any, Any]:
    """Used for direct migration execution (run/rollback/status) via the DI container.

    Prefers the DI-managed runner when the database provider is available so that
    connection pooling and observability hooks are active.  Falls back to the
    legacy factory when the package is not installed.

    Returns:
        A ``(runner, orchestrator, container)`` tuple so callers can
        shut down the provider lifecycle when finished.
    """
    import os

    db_url = os.environ.get("DATABASE_URL", "sqlite:///./dev.db")

    try:
        from quadkit.contracts.data.sql.migrations import MigrationRunnerProtocol
        from quadkit.di.container import Container
        from quadkit.di.orchestrator import ProviderOrchestrator

        sql_provider_mod = importlib.import_module(module_for("sql", "di.provider"))
        DBDIProvider = sql_provider_mod.DatabaseProvider

        container = Container()
        provider = DBDIProvider(config=db_url)
        # Same skip as _bootstrap_db_provider: the provider holds an explicit
        # DatabaseConfig; the bare CLI container has no QuadkitConfig.
        provider._config_from_factory = True  # noqa: SLF001 — bootstrap flag, mirrors Provider.from_config()
        orchestrator = ProviderOrchestrator(container)
        orchestrator.add(provider)
        await orchestrator.boot_all(container)
        runner = await container.resolve(MigrationRunnerProtocol)
        return runner, orchestrator, container

    except ImportError:
        # Database provider not installed — fall back to legacy direct factory.
        try:
            db_cli = importlib.import_module(module_for("sql", "cli"))
            manager = db_cli.create_cli_migration_manager(db_url)
            return manager, None, None
        except ImportError as e:
            out = OutputManager()
            out.error(
                f"The optional database provider is required for database commands ({e})"
            )
            raise typer.Exit(1) from None


async def _bootstrap_db_provider() -> tuple[Any, Any]:
    """Used by `db setup` to resolve a DatabaseProviderProtocol outside a full app boot.

    Registers and boots the DatabaseProvider directly against a fresh
    Container via a ProviderOrchestrator (same lifecycle as Application),
    then resolves DatabaseProviderProtocol.

    Returns:
        A ``(db, provider)`` tuple: the resolved database facade and the
        booted DatabaseProvider (so the caller can shut it down afterwards).
    """
    import os

    db_url = os.environ.get("DATABASE_URL", "sqlite:///./dev.db")
    try:
        from quadkit.contracts.data.sql.database import DatabaseProviderProtocol
        from quadkit.di.container import Container
        from quadkit.di.orchestrator import ProviderOrchestrator

        sql_provider_mod = importlib.import_module(module_for("sql", "di.provider"))
        DatabaseProvider = sql_provider_mod.DatabaseProvider
        sql_config_mod = importlib.import_module(module_for("sql", "config"))
        DatabaseConfig = sql_config_mod.DatabaseConfig

        container = Container()
        provider = DatabaseProvider(config=db_url)
        # Satisfy the orchestrator's config-injection phase: the provider
        # already holds an explicit DatabaseConfig (parsed from DATABASE_URL
        # in __init__), so the QuadkitConfig lookup — unavailable in this
        # bare CLI container — must be skipped.  `from_config()` marks the
        # same flag; we mark it here because the constructor already parsed
        # the URL into the provider's explicit config.
        provider._config_from_factory = True  # noqa: SLF001 — bootstrap flag, mirrors Provider.from_config()
        orchestrator = ProviderOrchestrator(container)
        orchestrator.add(provider)
        await orchestrator.boot_all(container)
        return await container.resolve(DatabaseProviderProtocol), provider

    except ImportError as e:
        out = OutputManager()
        out.error(
            f"The optional database provider is required for database commands ({e})"
        )
        raise typer.Exit(1) from None


async def get_migration_manager() -> Any:
    """Used for introspection/listing: resolves a legacy SimpleMigrationManager exposing the full manager API.

    Commands that only need run/rollback/status should use
    ``_bootstrap_migration_runner()`` to resolve MigrationRunnerProtocol
    through the DI container instead.
    """
    try:
        import os

        db_cli = importlib.import_module(module_for("sql", "cli"))
        db_url = os.environ.get("DATABASE_URL", "sqlite:///./dev.db")
        return db_cli.create_cli_migration_manager(db_url)
    except ImportError as e:
        out = OutputManager()
        out.error(f"Failed to import the optional database provider: {e}")
        raise typer.Exit(1) from None


__all__ = [
    "_bootstrap_db_provider",
    "_bootstrap_migration_runner",
    "get_migration_manager",
]
