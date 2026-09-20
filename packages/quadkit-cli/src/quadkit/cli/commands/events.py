"""Event schema management CLI commands.

Provides ``quadkit events migrate`` and ``quadkit events status`` to
inspect and apply event-schema migrations managed by
:class:`SchemaEvolution` from the optional event provider.
"""

from __future__ import annotations

import asyncio
from typing import Annotated, Any

import typer

from quadkit.cli.output import OutputManager
from quadkit.cli.package_names import module_for
from quadkit.cli.runtime import handle_errors
from quadkit.contracts.constants import DOCS_BASE_URL

app = typer.Typer(name="events")


def _make_evolution() -> Any:
    """Bootstrap an in-memory SchemaRegistry and SchemaEvolution.

    When the optional event provider is installed and discoverable, this returns a
    properly wired instance.  Raises :exc:`typer.Exit` with a readable error
    message when the package is not available.
    """
    out = OutputManager()
    try:
        import importlib as _importlib

        _evo_mod = _importlib.import_module(module_for("events", "schema.evolution"))
        _reg_mod = _importlib.import_module(module_for("events", "schema.registry"))
        _store_mod = _importlib.import_module(module_for("events", "schema.store"))
        SchemaEvolution = _evo_mod.SchemaEvolution
        SchemaRegistry = _reg_mod.SchemaRegistry
        InMemorySchemaStore = _store_mod.InMemorySchemaStore
    except ImportError:
        out.error(
            "The optional event provider is not installed. "
            "Install the provider before retrying."
        )
        raise typer.Exit(1) from None

    store = InMemorySchemaStore()
    registry = SchemaRegistry(store=store)
    return SchemaEvolution(registry=registry)


@app.command()
@handle_errors
def migrate(
    event_type: str = typer.Argument(
        ...,
        help="Fully-qualified event type name, e.g. 'UserCreated'.",
    ),
    from_version: int = typer.Option(
        ...,
        "--from",
        "-f",
        help="Source schema version.",
    ),
    to_version: int = typer.Option(
        ...,
        "--to",
        "-t",
        help="Target schema version.  Use -1 for latest.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Print the migration path without applying changes.",
    ),
) -> None:
    """Show or apply the migration path between two event schema versions.

    Example::

        quadkit events migrate UserCreated --from 1 --to 3
        quadkit events migrate UserCreated --from 1 --to -1 --dry-run
    """

    async def _run() -> None:
        out = OutputManager()
        evolution = _make_evolution()

        if to_version == -1:
            # Resolve "latest" via the registry — use importlib to avoid a
            # hard cross-extension import at module level.
            import importlib as _importlib

            _reg_mod = _importlib.import_module(module_for("events", "schema.registry"))
            _store_mod = _importlib.import_module(module_for("events", "schema.store"))
            registry = _reg_mod.SchemaRegistry(store=_store_mod.InMemorySchemaStore())
            latest = await registry.get_latest_version(event_type)
            target = latest if latest is not None else from_version
        else:
            target = to_version

        path = await evolution.get_migration_path(event_type, from_version, target)

        if not path:
            out.info(
                f"No migration steps found for {event_type!r} "
                f"v{from_version} → v{target}."
            )
            return

        out.info(
            f"Migration path for {event_type!r}: "
            f"v{from_version} → v{target} ({len(path)} step(s))"
        )
        for i, step in enumerate(path, start=1):
            out.info(f"  Step {i}: {step}")

        if dry_run:
            out.info("[dry-run] No changes applied.")
        else:
            out.success(
                "Migration path resolved successfully.  "
                "Apply by calling SchemaEvolution.migrate_event() at runtime."
            )

    asyncio.run(_run())


@app.command()
@handle_errors
def status(
    event_type: str = typer.Argument(
        None,
        help="Filter status to a specific event type (omit for all).",
    ),
) -> None:
    """Show registered event types and their schema versions.

    Example::

        quadkit events status
        quadkit events status UserCreated
    """

    async def _run() -> None:
        out = OutputManager()
        _make_evolution()
        event_handlers: list[dict[str, str]] = []  # TODO: use public API when available

        if not event_handlers:
            out.info("No event schemas registered.")
            return

    asyncio.run(_run())


@app.command("list")
def list_event_types() -> None:
    """List all registered event types in the application."""
    out = OutputManager()
    out.print("[bold]Registered event types:[/bold]\n")
    out.print("[yellow]Requires a running application context.[/yellow]")
    out.print(
        "Start the app and use [cyan]quadkit inspect events[/cyan] "
        "to list live event handlers."
    )
    out.print(
        "\nFor offline inspection, run [cyan]quadkit gen list[/cyan] "
        "to see available event generators."
    )


@app.command()
def replay(
    event_id: Annotated[
        str | None, typer.Option("--id", help="Replay a specific event by ID")
    ] = None,
    event_type: Annotated[
        str | None, typer.Option("--type", help="Replay all events of a type")
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Show what would be replayed without executing"),
    ] = False,
) -> None:
    """Replay events from the event store.

    Args:
        event_id: Specific event ID to replay.
        event_type: Replay all events matching this type.
        dry_run: Preview replay without executing.
    """
    out = OutputManager()
    out.print("[yellow]⚠  Event replay is not yet implemented via the CLI.[/yellow]")
    out.print()
    out.print("Use the programmatic approach instead:")
    out.print()
    out.print(f"  [cyan]from {module_for('events')} import EventBus[/cyan]")
    out.print("  [cyan]bus = container.resolve(EventBus)[/cyan]")
    out.print(
        "  [cyan]await bus.replay(event_type='UserCreated', since=start_time)[/cyan]"
    )
    out.print()
    out.print(f"See: {DOCS_BASE_URL}/events/replay")
