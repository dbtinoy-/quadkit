"""Migration lifecycle commands for the db command group."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

import typer

from quadkit.cli.commands import db_bootstrap
from quadkit.cli.output import OutputManager
from quadkit.cli.runtime import handle_errors


@handle_errors
def init(
    directory: str = typer.Argument("migrations", help="Migration directory"),
) -> None:
    """Initialize database migrations."""
    out = OutputManager()
    path = Path(directory)
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
        out.success(f"Created {directory} directory.")
    else:
        out.warning(f"Directory {directory} already exists.")


@handle_errors
def migrate(
    name: str = typer.Argument(..., help="Migration name"),
) -> None:
    """Generate a new migration file."""
    out = OutputManager()

    async def _run() -> None:
        manager = await db_bootstrap.get_migration_manager()
        version = await manager.create_migration(name, "-- Add your SQL here")
        out.success(f"Created migration {version}: {name}")

    asyncio.run(_run())


@handle_errors
def create(
    name: Annotated[
        str, typer.Argument(help="Migration name (e.g. 'add_users_table')")
    ],
    message: Annotated[
        str | None,
        typer.Option("--message", "-m", help="Migration description"),
    ] = None,
) -> None:
    """Create a new empty migration file.

    Args:
        name: Short name for the migration (snake_case).
        message: Optional longer description.
    """
    import asyncio

    out = OutputManager()

    async def _run() -> None:
        try:
            manager = await db_bootstrap.get_migration_manager()
            result = await manager.create(name=name, message=message or name)
            out.print(f"[green]Created migration:[/green] {result}")
        except Exception as exc:  # noqa: BLE001
            out.print(f"[red]Failed to create migration: {exc}[/red]")
            raise typer.Exit(1) from exc

    asyncio.run(_run())


@handle_errors
def upgrade(
    env: str | None = typer.Option("--env", "-e", help="Environment name"),
) -> None:
    """Apply pending migrations."""
    out = OutputManager()

    async def _run() -> None:
        (
            runner,
            orchestrator,
            _container,
        ) = await db_bootstrap._bootstrap_migration_runner()
        try:
            applied = await runner.run_migrations()
            if applied:
                for v in applied:
                    out.success(f"Applied {v}")
            else:
                out.info("No pending migrations.")
        finally:
            if orchestrator is not None:
                await orchestrator.shutdown_all()

    asyncio.run(_run())


@handle_errors
def downgrade(
    version: str | None = typer.Argument(None, help="Version to downgrade to"),
    env: str | None = typer.Option("--env", "-e", help="Environment name"),
) -> None:
    """Revert migrations."""
    out = OutputManager()

    async def _run() -> None:
        (
            runner,
            orchestrator,
            _container,
        ) = await db_bootstrap._bootstrap_migration_runner()
        try:
            current = await runner.get_current_version()
            if not current:
                out.info("No migrations to rollback.")
                return

            target = version  # None = roll back most recent
            out.info(f"Rolling back to: {target or 'previous'}")
            rolled_back = await runner.rollback(target)
            if rolled_back:
                for v in rolled_back:
                    out.success(f"Rolled back {v}")
            else:
                out.error("Rollback failed or version not found.")
        finally:
            if orchestrator is not None:
                await orchestrator.shutdown_all()

    asyncio.run(_run())


@handle_errors
def status(
    env: str | None = typer.Option("--env", "-e", help="Environment name"),
) -> None:
    """Show migration status."""
    out = OutputManager()

    async def _run() -> None:
        (
            runner,
            orchestrator,
            _container,
        ) = await db_bootstrap._bootstrap_migration_runner()
        try:
            current = await runner.get_current_version()
            pending = await runner.get_pending_migrations()

            if current:
                out.print(f"[green]Current version:[/green] {current}")
            else:
                out.warning("No migrations applied yet.")

            if pending:
                out.warning(f"\nPending migrations: {len(pending)}")
                for p in pending:
                    out.print(f"  ? {p}")
            else:
                out.print("[green]Schema is up to date.[/green]")
        finally:
            if orchestrator is not None:
                await orchestrator.shutdown_all()

    asyncio.run(_run())


@handle_errors
def history(
    limit: int = typer.Option(20, "--limit", "-n", help="Number of migrations to show"),
    env: str | None = typer.Option("--env", "-e", help="Environment name"),
) -> None:
    """Show migration history."""
    out = OutputManager()

    async def _run() -> None:
        manager = await db_bootstrap.get_migration_manager()
        await manager.provider.boot()
        try:
            applied = await manager.get_applied_migrations()
            if not applied:
                out.info("No migration history found.")
                return

            out.print(f"[bold]Migration History (last {limit}):[/bold]")
            for _i, m in enumerate(reversed(applied[-limit:])):
                status_icon = "[green]↑[/green]" if m.success else "[red]↓[/red]"
                out.print(f"{status_icon} {m.version} - {m.name}")
        finally:
            await manager.provider.shutdown()

    asyncio.run(_run())


@handle_errors
def validate(
    env: str | None = typer.Option("--env", "-e", help="Environment name"),
) -> None:
    """Validate migrations."""
    out = OutputManager()

    async def _run() -> None:
        manager = await db_bootstrap.get_migration_manager()
        await manager.provider.boot()
        try:
            await manager.initialize_migration_table()
            applied = await manager.get_applied_migrations()

            issues: list[str] = []

            if not manager.migrations_dir.exists():
                issues.append("Migrations directory does not exist")

            available = []
            if manager.migrations_dir.exists():
                available = sorted(
                    [
                        f.stem
                        for f in manager.migrations_dir.glob("*.sql")
                        if not f.name.endswith(".down.sql")
                    ],
                )

            {m.version for m in applied}
            for m in applied:
                if m.version not in available and m.version != "init":
                    issues.append(
                        f"Applied migration '{m.version}' has no corresponding file",
                    )

            if issues:
                out.error("Migration validation failed:")
                for issue in issues:
                    out.print(f"  • {issue}")
                raise typer.Exit(1)
            out.success("Migration validation passed!")
            out.print(f"  Applied migrations: {len(applied)}")
            out.print(f"  Available migrations: {len(available)}")
        finally:
            await manager.provider.shutdown()

    asyncio.run(_run())


__all__ = [
    "create",
    "downgrade",
    "history",
    "init",
    "migrate",
    "status",
    "upgrade",
    "validate",
]
