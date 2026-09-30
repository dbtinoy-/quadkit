"""Seed, reset, and schema-setup commands for the db command group."""

from __future__ import annotations

import asyncio
import importlib
import importlib.util
from pathlib import Path
import sys
from typing import Annotated

import typer

from quadkit.cli.commands import db_bootstrap
from quadkit.cli.layout import read_project_layout, resolve_output_dir
from quadkit.cli.output import OutputManager
from quadkit.cli.runtime import handle_errors
from quadkit.contracts.cli.contributions import (
    SchemaSetupContribution,
    SchemaSetupOutcome,
    SchemaSetupResult,
)
from quadkit.contracts.data.sql.database import DatabaseProviderProtocol


def _seeder_sources() -> list[tuple[Path, str | None]]:
    """Every directory this project keeps seeders in, and how to import each.

    Resolution order:

    1. the canonical ``seeders`` component — where ``quadkit gen seeder``
       writes and where a generated application keeps the seeders its
       persistence provider boots;
    2. **one per bounded context** — ``src/<app>/modules/<slug>/seeders``.
       A seeder seeds one entity, so it follows that entity into its module
       (OQ-L1). Before that, every seeder in a modular project shared one
       ``shared/seeders`` directory and a single lookup found them all;
       scanning the modules is what keeps ``db seed`` complete now that they
       are spread out. Missing this is how the command would silently seed
       nothing in exactly the projects that need it most;
    3. the project-root ``seeds/`` directory — what a project generated
       before the ``seeders`` row landed has, and what a hand-written
       collection looks like. Those files sit outside any package, so they
       stay path-loaded, exactly as this command always loaded them.

    Returns:
        ``(directory, module_prefix)`` pairs: the directory to read, and the
        dotted package its modules belong to when it lives inside ``src/`` —
        ``None`` when it does not, which is the signal to load by path.
    """
    layout = read_project_layout()
    found: list[tuple[Path, str | None]] = []

    canonical = Path(resolve_output_dir("src/seeders", app_package=layout.app_package))
    if canonical.is_dir():
        found.append((canonical, _module_prefix(canonical)))

    # The app package's `modules/` tree, if this project has bounded contexts.
    app_root = canonical.parent if canonical.name == "seeders" else None
    modules_root = (app_root / "modules") if app_root else None
    if modules_root and modules_root.is_dir():
        for module_dir in sorted(modules_root.iterdir()):
            seeders = module_dir / "seeders"
            if seeders.is_dir():
                found.append((seeders, _module_prefix(seeders)))

    if found:
        return found
    # The legacy root directory is returned whether or not it exists: the
    # callers report "no seeds directory found" from it, so handing back an
    # absent path is how that message still gets made.
    return [(Path("seeds"), None)]


def _seeder_source() -> tuple[Path, str | None]:
    """The first seeder directory, for callers that only report existence."""
    return _seeder_sources()[0]


def _module_prefix(directory: Path) -> str | None:
    """Dotted package name for *directory*, when it is inside ``src/``."""
    parts = directory.parts
    if "src" not in parts:
        return None
    after_src = parts[parts.index("src") + 1 :]
    return ".".join(after_src) if after_src else None


def _make_importable(directory: Path) -> None:
    """Put the package root of *directory* on ``sys.path``.

    Seeders import the application's own packages (``from my_app.shared...``),
    and the CLI is not run with the project's ``src`` on the path the way the
    project's own entry point is.
    """
    parts = directory.parts
    if "src" not in parts:
        return
    root = Path(*parts[: parts.index("src") + 1])
    resolved = str(root.resolve())
    if resolved not in sys.path:
        sys.path.insert(0, resolved)


def _seed_files(directory: Path) -> list[Path]:
    """Seeders to run, in filename order.

    ``__init__.py`` is skipped: seeders below ``src/`` live in a package, and
    the package marker is not a seeder -- running it would report "No 'run'
    function found" for a file the user never wrote.
    """
    return [
        path for path in sorted(directory.glob("*.py")) if path.name != "__init__.py"
    ]


async def _run_seeder(
    out: OutputManager,
    provider: DatabaseProviderProtocol,
    seed_file: Path,
    module_prefix: str | None,
) -> None:
    """Execute one seeder file.

    A seeder inside the application package is *imported*: it is an ordinary
    module there, and importing is what the generated application itself does
    when it boots its seeders. Anything else is loaded from its path, which is
    the only thing that works for a file outside ``src/``.
    """
    out.info(f"Running seeder: {seed_file}")

    if module_prefix is not None:
        _make_importable(seed_file)
        module = importlib.import_module(f"{module_prefix}.{seed_file.stem}")
    else:
        spec = importlib.util.spec_from_file_location("seed_module", seed_file)
        if spec is None or spec.loader is None:
            out.warning(f"Could not load seeder: {seed_file}")
            return
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

    if not hasattr(module, "run"):
        out.warning(f"No 'run' function found in {seed_file}")
        return

    if asyncio.iscoroutinefunction(module.run):
        await module.run(provider)
    else:
        module.run(provider)
    out.success(f"Seeder {seed_file} completed.")


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
            sources = _seeder_sources()
            seeds_dir = sources[0][0]
            if not any(d.exists() for d, _ in sources) and not file:
                out.warning("No seeds directory found.")
                return

            # Annotated: the first branch appends ``(path, None)`` and the
            # second rebuilds with a module prefix, so inference from the
            # empty list would pin the tuple's second element to ``None``.
            files_to_run: list[tuple[Path, str | None]] = []
            if file:
                # An explicit file is run as given, by path: the user named a
                # file, not a module.
                files_to_run.append((Path(file), None))
            else:
                files_to_run = [
                    (seed_file, prefix)
                    for directory, prefix in _seeder_sources()
                    for seed_file in _seed_files(directory)
                ]

            for seed_file, prefix in files_to_run:
                await _run_seeder(out, manager.provider, seed_file, prefix)

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
                sources = _seeder_sources()
                if any(d.exists() for d, _ in sources):
                    for directory, prefix in sources:
                        for seed_file in _seed_files(directory):
                            await _run_seeder(out, manager.provider, seed_file, prefix)
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
