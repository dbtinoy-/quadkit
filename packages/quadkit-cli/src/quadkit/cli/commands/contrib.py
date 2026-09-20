"""CLI contributor discovery commands.

Provides ``quadkit contrib list`` and ``quadkit contrib inspect`` which
discover installed CLI contributors registered under the
``quadkit.cli.contributors`` entry-point group and report their full
contribution surface (generators, commands, health checks, doctor checks,
shell context, and hooks).  No DI container is required — discovery runs
directly against the installed package metadata at runtime.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import typer

from quadkit.cli.contributors.runtime import ContributorRuntime
from quadkit.cli.output import OutputManager

app = typer.Typer(
    name="contrib",
    help="Discover and inspect installed CLI contributors",
    no_args_is_help=True,
)


def _names_preview(items: Sequence[object], attr: str, limit: int = 5) -> str:
    """Return a short comma-separated preview of *attr* on each item.

    Args:
        items: List of contribution objects.
        attr: Attribute name to read from each item (e.g. ``"name"``).
        limit: Maximum items to show before appending an overflow indicator.

    Returns:
        A display string, e.g. ``"foo, bar, baz, … (+2 more)"``.
    """
    names = [getattr(item, attr, "?") for item in items[:limit]]
    preview = ", ".join(str(n) for n in names)
    overflow = len(items) - limit
    if overflow > 0:
        preview += f", … (+{overflow} more)"
    return preview


@app.command("list")
def plugin_list(
    json: bool = typer.Option(False, "--json", help="Output in JSON format"),
) -> None:
    """List installed CLI contributors and their contribution surface.

    Discovers all packages that have registered an entry point under the
    ``quadkit.cli.contributors`` group, loads each contributor, and prints
    a summary of every contribution type it exposes.

    Example output::

        Installed CLI contributors:
          core  (built-in)  19 gen | 0 cmd | 1 health | 1 doctor
          sql               4 gen  | 1 cmd | 1 health | 2 doctor

    No DI container is required; discovery runs entirely from package
    metadata at import time.
    """
    out = OutputManager(json_mode=json)

    runtime = ContributorRuntime.from_entry_points()

    if not runtime.contributors and not runtime.errors:
        out.print("No CLI contributors found.")
        return

    out.print("[bold]Installed CLI contributors:[/bold]\n")

    for contributor in runtime.contributors:
        label = contributor.contributor_id
        tag = "  [dim](built-in)[/dim]" if label == "core" else ""

        generators = contributor.get_generators()
        commands: Any = getattr(contributor, "get_commands", list)()
        health_checks: Any = getattr(contributor, "get_health_checks", list)()
        doctor_checks: Any = getattr(contributor, "get_doctor_checks", list)()
        shell_ctx: Any = getattr(contributor, "get_shell_context", list)()
        hooks: Any = getattr(contributor, "get_hooks", list)()

        out.print(
            f"  [cyan]{label}[/cyan]{tag}  "
            f"[bold]{len(generators)}[/bold] gen  "
            f"[bold]{len(commands)}[/bold] cmd  "
            f"[bold]{len(health_checks)}[/bold] health  "
            f"[bold]{len(doctor_checks)}[/bold] doctor  "
            f"[bold]{len(shell_ctx)}[/bold] shell  "
            f"[bold]{len(hooks)}[/bold] hooks"
        )
        if generators:
            out.print(
                f"    [dim]generators: {_names_preview(generators, 'name')}[/dim]"
            )

    for error in runtime.errors.values():
        out.print(f"  [red]✗[/red] {error.contributor_id}: {error.exception}")

    if runtime.command_conflicts:
        out.print("\n[bold]Command conflicts:[/bold]")
        for conflict in runtime.command_conflicts.values():
            out.print(
                f"  [yellow]⚠[/yellow] {conflict.name}: "
                f"[green]{conflict.winner}[/green] wins over "
                f"{', '.join(conflict.losers)}"
            )


@app.command("inspect")
def plugin_inspect(
    name: str = typer.Argument(
        ..., help="Contributor ID to inspect (e.g. 'sql', 'auth')"
    ),
) -> None:
    """Show full contribution details for a specific contributor.

    Args:
        name: The contributor_id to inspect (matches the entry point key).
    """
    out = OutputManager()

    runtime = ContributorRuntime.from_entry_points()
    contributor = next(
        (c for c in runtime.contributors if c.contributor_id == name), None
    )

    if contributor is None:
        available = ", ".join(sorted(c.contributor_id for c in runtime.contributors))
        if runtime.errors:
            available += f" (errors: {', '.join(runtime.errors)})"
        out.print(f"[red]Contributor '{name}' not found.[/red]")
        out.print(f"Available: {available}")
        raise typer.Exit(1)

    tag = " (built-in)" if name == "core" else ""
    out.print(f"[bold cyan]{name}[/bold cyan]{tag}\n")

    generators: list[Any] = getattr(contributor, "get_generators", list)()
    if generators:
        out.print(f"[bold]Generators ({len(generators)}):[/bold]")
        for g in generators:
            out.print(f"  [cyan]{g.name}[/cyan]  {g.description}")

    commands: list[Any] = getattr(contributor, "get_commands", list)()
    if commands:
        out.print(f"\n[bold]Commands ({len(commands)}):[/bold]")
        for c in commands:
            out.print(f"  [cyan]quadkit {c.name}[/cyan]  {c.help}")

    health_checks = contributor.get_health_checks()
    if health_checks:
        out.print(f"\n[bold]Health checks ({len(health_checks)}):[/bold]")
        for h in health_checks:
            critical_tag = " [red](critical)[/red]" if h.critical else ""
            out.print(f"  [cyan]{h.name}[/cyan]{critical_tag}  {h.description}")

    doctor_checks = contributor.get_doctor_checks()
    if doctor_checks:
        out.print(f"\n[bold]Doctor checks ({len(doctor_checks)}):[/bold]")
        for d in doctor_checks:
            fixable_tag = " [green](auto-fix)[/green]" if d.can_fix else ""
            out.print(f"  [cyan]{d.name}[/cyan]{fixable_tag}  {d.description}")

    shell_ctx = contributor.get_shell_context()
    if shell_ctx:
        out.print(f"\n[bold]Shell context ({len(shell_ctx)}):[/bold]")
        for s in shell_ctx:
            out.print(f"  [cyan]{s.name}[/cyan]  {s.description}")

    hook_items = contributor.get_hooks()
    if hook_items:
        out.print(f"\n[bold]Hooks ({len(hook_items)}):[/bold]")
        for hook in hook_items:
            out.print(
                f"  [cyan]{hook.event}[/cyan]  priority={hook.priority}  {hook.handler_path}"
            )


@app.command("check")
def plugin_check(
    json: bool = typer.Option(False, "--json", help="Output in JSON format"),
) -> None:
    """Verify all installed contributors load without errors.

    Loads each registered contributor and reports any that fail.
    Exit code is 1 if any contributor fails to load.
    """
    out = OutputManager(json_mode=json)

    runtime = ContributorRuntime.from_entry_points()

    total = len(runtime.contributors) + len(runtime.errors)
    if total == 0:
        if json:
            print(
                '{"status": "ok", "message": "No contributors found.", "contributors": [], "errors": [], "conflicts": []}'
            )
        else:
            out.print("[yellow]No contributors found.[/yellow]")
        return

    if json:
        payload = {
            "status": "ok" if not runtime.errors else "error",
            "contributors": [
                contributor.contributor_id for contributor in runtime.contributors
            ],
            "errors": [
                {
                    "contributor_id": e.contributor_id,
                    "stage": e.stage,
                    "exception": e.exception,
                }
                for e in runtime.errors.values()
            ],
            "conflicts": [
                {
                    "name": c.name,
                    "winner": c.winner,
                    "losers": list(c.losers),
                }
                for c in runtime.command_conflicts.values()
            ],
        }
        from quadkit.serialization import dumps_str

        print(dumps_str(payload))
    else:
        out.print(f"[bold]Checking {total} contributor(s)...[/bold]\n")

        for contributor in runtime.contributors:
            out.print(f"  [green]✓[/green] {contributor.contributor_id}")

        for error in runtime.errors.values():
            out.print(f"  [red]✗[/red] {error.contributor_id}: {error.exception}")

        for conflict in runtime.command_conflicts.values():
            out.print(
                f"  [yellow]⚠[/yellow] {conflict.name}: "
                f"[green]{conflict.winner}[/green] wins over "
                f"{', '.join(conflict.losers)}"
            )

        out.print("")
        if runtime.errors:
            out.print(f"[red]{len(runtime.errors)} contributor(s) failed.[/red]")
            raise typer.Exit(1)
        out.print(
            f"[green]All {len(runtime.contributors)} contributor(s) healthy.[/green]"
        )


__all__ = ["app", "plugin_check", "plugin_inspect", "plugin_list"]
