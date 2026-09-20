"""Runtime inspection commands.

This module provides commands for inspecting the runtime state of a Quadkit application.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Annotated

import typer

from quadkit.cli.output import OutputManager
from quadkit.cli.runtime import handle_errors

app = typer.Typer(
    name="inspect",
    help="Inspect runtime state of the application",
)


@app.command("providers")
@handle_errors
def inspect_providers(
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Show detailed info"),
    ] = False,
) -> None:
    """List all registered providers."""
    out = OutputManager()

    out.print("[yellow]⚠  Not yet implemented.[/yellow]")
    out.print()
    out.print("Inspect commands require runtime introspection infrastructure")
    out.print("that is not yet available.")
    out.print()
    out.print("[dim]These commands will show real data in a future release.[/dim]")


@app.command("routes")
@handle_errors
def inspect_routes(
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Show middleware and guards"),
    ] = False,
    method: Annotated[
        str | None,
        typer.Option("--method", "-m", help="Filter by HTTP method"),
    ] = None,
) -> None:
    """List all HTTP routes."""
    out = OutputManager()

    out.print("[yellow]⚠  Not yet implemented.[/yellow]")
    out.print()
    out.print("Inspect commands require runtime introspection infrastructure")
    out.print("that is not yet available.")
    out.print()
    out.print("[dim]These commands will show real data in a future release.[/dim]")


@app.command("middleware")
@handle_errors
def inspect_middleware() -> None:
    """List middleware stack in order."""
    out = OutputManager()

    out.print("[yellow]⚠  Not yet implemented.[/yellow]")
    out.print()
    out.print("Inspect commands require runtime introspection infrastructure")
    out.print("that is not yet available.")
    out.print()
    out.print("[dim]These commands will show real data in a future release.[/dim]")


@app.command("container")
@handle_errors
def inspect_container(
    scope: Annotated[
        str | None,
        typer.Option("--scope", help="Filter by scope"),
    ] = None,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Show resolution details"),
    ] = False,
) -> None:
    """Show DI container registrations."""
    out = OutputManager()

    out.print("[yellow]⚠  Not yet implemented.[/yellow]")
    out.print()
    out.print("Inspect commands require runtime introspection infrastructure")
    out.print("that is not yet available.")
    out.print()
    out.print("[dim]These commands will show real data in a future release.[/dim]")


@app.command("events")
@handle_errors
def inspect_events() -> None:
    """List registered event handlers."""
    out = OutputManager()

    out.print("[yellow]⚠  Not yet implemented.[/yellow]")
    out.print()
    out.print("Inspect commands require runtime introspection infrastructure")
    out.print("that is not yet available.")
    out.print()
    out.print("[dim]These commands will show real data in a future release.[/dim]")


@app.command("tasks")
@handle_errors
def inspect_tasks() -> None:
    """List registered task handlers."""
    out = OutputManager()

    out.print("[yellow]⚠  Not yet implemented.[/yellow]")
    out.print()
    out.print("Inspect commands require runtime introspection infrastructure")
    out.print("that is not yet available.")
    out.print()
    out.print("[dim]These commands will show real data in a future release.[/dim]")


@app.command("dependencies")
@handle_errors
def inspect_dependencies(
    file_format: Annotated[
        str,
        typer.Option("--format", "-f", help="Output format"),
    ] = "text",
) -> None:
    """Show provider dependency graph."""
    out = OutputManager()

    out.print("[yellow]⚠  Not yet implemented.[/yellow]")
    out.print()
    out.print("Inspect commands require runtime introspection infrastructure")
    out.print("that is not yet available.")
    out.print()
    out.print("[dim]These commands will show real data in a future release.[/dim]")


@app.command("config")
@handle_errors
def inspect_config() -> None:
    """Alias for config show."""
    from quadkit.cli.commands.config import show as config_show

    config_show()


def _print_needs_context(out: OutputManager, command: str, detail: str) -> None:
    """Print a consistent 'needs running context' message for stub inspect commands.

    Args:
        out: The OutputManager instance to write to.
        command: The CLI command path, e.g. ``"inspect modules"``.
        detail: One-line description of what the command shows when live.
    """
    out.print(f"[bold]quadkit {command}[/bold]")
    out.print()
    out.print(f"[dim]{detail}[/dim]")
    out.print()
    out.print("[yellow]Requires a running application context.[/yellow]")
    out.print("Note: Run this command from a project directory with application.yaml")


@app.command("modules")
@handle_errors
def inspect_modules() -> None:
    """List all registered Quadkit modules in the application."""
    out = OutputManager()
    _print_needs_context(
        out,
        "inspect modules",
        "Shows all Module classes registered with the container.",
    )


@app.command("health")
@handle_errors
def inspect_health() -> None:
    """Show provider health status from the running application."""
    out = OutputManager()
    _print_needs_context(
        out,
        "inspect health",
        "Shows health status for each registered provider.",
    )


@app.command()
@handle_errors
def main(
    target: Annotated[
        str,
        typer.Argument(
            help="What to inspect (providers, routes, middleware, container, events, tasks, dependencies)",
        ),
    ] = "providers",
) -> None:
    """Inspect runtime state (alias for subcommands)."""
    out = OutputManager()

    commands: Mapping[str, Callable[[], None]] = {
        "providers": inspect_providers,
        "routes": inspect_routes,
        "middleware": inspect_middleware,
        "container": inspect_container,
        "events": inspect_events,
        "tasks": inspect_tasks,
        "dependencies": inspect_dependencies,
        "modules": inspect_modules,
        "health": inspect_health,
    }

    if target in commands:
        commands[target]()
    else:
        out.error(f"Unknown inspection target: {target}")
        out.print("Available: " + ", ".join(commands.keys()))
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
