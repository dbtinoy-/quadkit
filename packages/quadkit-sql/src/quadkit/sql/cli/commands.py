"""SQL CLI command group factory.

Note: The ``db`` command name is registered as a built-in by ``quadkit-cli``
and will NOT be dynamically re-registered via the contributor system.  This
factory exists so the ``app_factory_path`` declared in
``SqlCliContributor.get_commands()`` resolves to a valid callable — useful for
``quadkit contrib inspect sql`` and any tooling that introspects contributed
command surfaces.
"""

from __future__ import annotations

import typer


def create_db_app() -> typer.Typer:
    """Create the ``quadkit db`` command group.

    Returns:
        A Typer app containing database migration and management subcommands.
    """
    app = typer.Typer(help="Database migration and management commands")

    migrate_app = typer.Typer(help="Migration management commands")
    app.add_typer(migrate_app, name="migrate")

    @app.command("status")
    def status() -> None:
        """Show current database and migration status."""
        typer.echo("Database status not yet implemented")

    @migrate_app.command("run")
    def migrate_run(
        target: str | None = typer.Option(
            None, "--target", help="Target migration revision (default: head)"
        ),
    ) -> None:
        """Apply pending migrations."""
        typer.echo("Migration run not yet implemented")

    @migrate_app.command("rollback")
    def migrate_rollback(
        steps: int = typer.Option(1, "--steps", help="Number of migrations to revert"),
    ) -> None:
        """Roll back applied migrations."""
        typer.echo("Migration rollback not yet implemented")

    @migrate_app.command("history")
    def migrate_history() -> None:
        """Show migration history."""
        typer.echo("Migration history not yet implemented")

    @app.command("seed")
    def seed(
        env: str = typer.Option("development", "--env", help="Environment to seed"),
    ) -> None:
        """Run database seeders."""
        typer.echo("Database seeding not yet implemented")

    return app
