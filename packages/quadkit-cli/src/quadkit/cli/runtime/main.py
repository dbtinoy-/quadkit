"""Quadkit CLI entry point."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from quadkit.cli.commands import (
    add,
    config,
    contrib,
    db,
    dev,
    events,
    gen,
    init,
    inspect,
    meta,
    new,
    project,
    run,
    shell,
    system,
)
from quadkit.cli.runtime import CLIContext

app = typer.Typer(
    name="quadkit",
    help="Quadkit Framework CLI — build, run, and manage Quadkit applications.",
    add_completion=True,
    invoke_without_command=True,
    rich_markup_mode="rich",
)

# Register command groups
app.add_typer(init.app, name="init", help="Initialize Quadkit in existing project")
app.add_typer(new.app, name="new", help="Create a new Quadkit project")
app.add_typer(add.app, name="add", help="Add a provider to the project")
app.add_typer(dev.app, name="dev", help="Development server and tools")
app.add_typer(
    run.app, name="run", help="Smart runner — auto-detects factory, sets profile"
)
app.add_typer(db.app, name="db", help="Database management commands")
app.add_typer(events.app, name="events", help="Event schema management commands")
app.add_typer(gen.app, name="gen", help="Code generation commands")
app.add_typer(config.app, name="config", help="Configuration management")
app.add_typer(inspect.app, name="inspect", help="Inspect runtime state")
app.add_typer(shell.app, name="shell", help="Interactive Python REPL")
app.add_typer(
    contrib.app, name="contrib", help="Discover and inspect installed contributors"
)
app.add_typer(
    project.app,
    name="project",
    help="Project management (test, lint, routes)",
)
app.add_typer(system.app, name="system", help="System information and management")

# Register built-in meta commands
app.command()(meta.version)
app.command()(meta.completion)
app.command("list")(meta.list_commands)
app.command()(meta.test)
app.command()(meta.lint)


# ---------------------------------------------------------------------------
# Dynamic contributed command groups (from installed packages)
# ---------------------------------------------------------------------------


_BUILTIN_COMMANDS: frozenset[str] = frozenset(
    {
        "init",
        "new",
        "add",
        "dev",
        "run",
        "db",
        "events",
        "gen",
        "config",
        "inspect",
        "shell",
        "contrib",
        "project",
        "system",
        "version",
        "list",
        "health",
        "doctor",
        "test",
        "lint",
        "completion",
    }
)


def _load_contributed_commands() -> None:
    """Register command groups contributed by installed packages."""
    from quadkit.cli.contributors.runtime import ContributorRuntime  # noqa: PLC0415

    runtime = ContributorRuntime.from_entry_points()
    runtime.register_commands(app, _BUILTIN_COMMANDS)


_load_contributed_commands()


@app.callback()
def main(
    ctx: typer.Context,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output in JSON format"),
    ] = False,
    quiet: Annotated[
        bool,
        typer.Option("--quiet", "-q", help="Suppress non-essential output"),
    ] = False,
    debug: Annotated[
        bool,
        typer.Option("--debug", help="Show debug output and tracebacks"),
    ] = False,
    no_color: Annotated[
        bool,
        typer.Option("--no-color", help="Disable colored output"),
    ] = False,
    config_path: Annotated[
        Path | None,
        typer.Option("--config", "-c", help="Path to application.yaml"),
    ] = None,
) -> None:
    """The Quadkit Framework CLI."""
    # Typer's no_args_is_help exits with code 2 (usage error) and never
    # runs this callback; handle the bare invocation here instead so a
    # no-args ``quadkit`` prints full help and exits cleanly with 0.
    if ctx.invoked_subcommand is None and not ctx.resilient_parsing:
        typer.echo(ctx.get_help())
        raise typer.Exit(code=0)
    ctx.ensure_object(dict)
    ctx.obj["cli_context"] = CLIContext(
        json_mode=json_output,
        quiet=quiet,
        debug=debug,
        no_color=no_color,
        config_path=config_path,
    )


if __name__ == "__main__":
    app()
