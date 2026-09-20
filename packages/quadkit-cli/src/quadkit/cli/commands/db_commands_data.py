"""Seed, reset, and schema-setup commands for the db command group."""

from __future__ import annotations

import asyncio
import importlib
import importlib.util
from pathlib import Path
from typing import Annotated

import typer

from quadkit.cli.commands import db_bootstrap
from quadkit.cli.output import OutputManager
from quadkit.cli.runtime import handle_errors
from quadkit.contracts.cli.contributions import (
    SchemaSetupContribution,
    SchemaSetupOutcome,
    SchemaSetupResult,
)
from quadkit.contracts.data.sql.database import DatabaseProviderProtocol


@handle_errors
def seed(
    file: str | None = typer.Argument(None, help="Specific seed file to run"),
    env: str | None = typer.Option("--env", "-e", help="Environment name"),
) -> None:
    """Run database seeders."""
    out = OutputManager()

    async def _run() -> None:
        manager = await db_bootstrap.get_migration_manager()
        await manager.provider.boot()
        try:
            seeds_dir = Path("seeds")
            if not seeds_dir.exists() and not file:
                out.warning("No seeds directory found.")
                return

            files_to_run = []
            if file:
                files_to_run.append(Path(file))
            else:
                files_to_run = sorted(seeds_dir.glob("*.py"))

            for seed_file in files_to_run:
                out.info(f"Running seeder: {seed_file}")

                spec = importlib.util.spec_from_file_location("seed_module", seed_file)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                    if hasattr(module, "run"):
                        if asyncio.iscoroutinefunction(module.run):
                            await module.run(manager.provider)
                        else:
                            module.run(manager.provider)
                        out.success(f"Seeder {seed_file} completed.")
                    else:
                        out.warning(f"No 'run' function found in {seed_file}")

        except Exception as e:  # noqa: BLE001 — any seeder failure is a CLI error
            out.error(f"Seeder failed: {e}")
            raise typer.Exit(1) from None
        finally:
            await manager.provider.shutdown()

    asyncio.run(_run())


@handle_errors
def reset(
    seed: bool = typer.Option(False, "--seed", help="Run seeders after reset"),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Force reset without confirmation",
    ),
    env: str | None = typer.Option("--env", "-e", help="Environment name"),
) -> None:
    """Drop and recreate the database."""
    out = OutputManager()
    if not force:
        confirm = typer.confirm(
            "Are you sure you want to reset the database? This will delete ALL data.",
        )
        if not confirm:
            raise typer.Abort

    async def _run() -> None:
        manager = await db_bootstrap.get_migration_manager()
        await manager.provider.boot()
        try:
            out.info("Resetting database...")

            if "sqlite" in str(manager.provider.url):
                res = await manager.provider.execute_query(
                    "SELECT name FROM sqlite_master WHERE type='table'",
                )
                tables = [row["name"] for row in res.rows]
                for table in tables:
                    if table != "sqlite_sequence":
                        out.print(f"[dim]Dropping table: {table}[/dim]")
                        await manager.provider.execute(f"DROP TABLE {table}")
            else:
                out.warning(
                    "Reset is only fully optimized for SQLite currently.",
                )

            out.success("Database cleared.")

            await manager.initialize_migration_table()
            applied = await manager.apply_pending_migrations()
            if applied:
                for v in applied:
                    out.success(f"Applied {v}")
            else:
                out.info("No pending migrations.")

            if seed:
                seeds_dir = Path("seeds")
                if seeds_dir.exists():
                    files_to_run = sorted(seeds_dir.glob("*.py"))
                    for seed_file in files_to_run:
                        out.info(f"Running seeder: {seed_file}")

                        spec = importlib.util.spec_from_file_location(
                            "seed_module",
                            seed_file,
                        )
                        if spec and spec.loader:
                            module = importlib.util.module_from_spec(spec)
                            spec.loader.exec_module(module)
                            if hasattr(module, "run"):
                                if asyncio.iscoroutinefunction(module.run):
                                    await module.run(manager.provider)
                                else:
                                    module.run(manager.provider)
                                out.success(f"Seeder {seed_file} completed.")
                else:
                    out.warning("No seeds directory found, skipping seed step.")

        except Exception as e:  # noqa: BLE001 — any reset failure is a CLI error
            out.error(f"Reset failed: {e}")
            raise typer.Exit(1) from None
        finally:
            await manager.provider.shutdown()

    asyncio.run(_run())


@handle_errors
def setup(
    package: Annotated[
        str | None,
        typer.Option(
            "--package", help="Only run setup for this package's contributions."
        ),
    ] = None,
) -> None:
    """Run schema setup for all installed packages that need database tables."""
    asyncio.run(_run_setup(package))


async def _run_setup(package: str | None) -> None:
    from quadkit.cli.contributors.runtime import ContributorRuntime

    out = OutputManager()
    runtime = ContributorRuntime.from_entry_points()
    contributions = runtime.schema_setups
    if package:
        contributions = [c for c in contributions if c.name.split(".")[0] == package]

    if not contributions:
        out.info("Nothing to do — no schema setup contributions discovered.")
        return

    db, provider = await db_bootstrap._bootstrap_db_provider()

    failed = False
    try:
        for contribution in contributions:
            outcome = await _run_one_schema_setup(contribution, db)
            if outcome.status == SchemaSetupResult.CREATED:
                out.success(f"{contribution.name}: created")
            elif outcome.status == SchemaSetupResult.ALREADY_PRESENT:
                out.info(f"{contribution.name}: already present")
            else:
                out.error(f"{contribution.name}: failed — {outcome.message}")
                failed = True
    finally:
        await provider.shutdown()

    if failed:
        raise typer.Exit(1)


async def _run_one_schema_setup(
    contribution: SchemaSetupContribution,
    db: DatabaseProviderProtocol,
) -> SchemaSetupOutcome:
    try:
        module_path, _, fn_name = contribution.setup_fn_path.partition(":")
        mod = importlib.import_module(module_path)
        ensure_fn = getattr(mod, fn_name)
        outcome: SchemaSetupOutcome = await ensure_fn(db)
        return outcome
    except Exception as exc:
        return SchemaSetupOutcome(status=SchemaSetupResult.FAILED, message=str(exc))


__all__ = ["reset", "seed", "setup"]
