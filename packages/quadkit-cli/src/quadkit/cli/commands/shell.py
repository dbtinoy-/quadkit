"""Interactive Python REPL commands.

This module provides an interactive shell with the Quadkit application context pre-loaded.
"""

from __future__ import annotations

from typing import Annotated

import typer

from quadkit.cli.output import OutputManager
from quadkit.cli.runtime import handle_errors

app = typer.Typer(
    name="shell",
    help="Interactive Python REPL with app context",
)


def _banner() -> str:
    return """
[bold green]Quadkit Interactive Shell[/bold green]

Available objects:
  app        - Application instance
  container  - DI container
  config     - Resolved configuration
  db         - Database session (if db enabled)
  cache      - Cache service (if cache enabled)
  events     - Event bus (if events enabled)

Type 'exit()' or Ctrl-D to exit.
"""


@app.command()
@handle_errors
def main(
    no_app: Annotated[
        bool,
        typer.Option("--no-app", help="Plain Python REPL without app bootstrap"),
    ] = False,
    ipython: Annotated[
        bool,
        typer.Option("--ipython", help="Use IPython if available"),
    ] = False,
) -> None:
    """Start an interactive Python REPL."""
    out = OutputManager()

    out.print(_banner())

    if no_app:
        out.print("[yellow]Running without app bootstrap[/yellow]")
        _run_plain_repl(ipython)
        return

    try:
        _run_repl_with_app(ipython)
    except FileNotFoundError:
        out.error(
            "No application.yaml found.",
            hint="Run from a project directory or use --no-app",
        )
        raise typer.Exit(1) from None


def _run_plain_repl(use_ipython: bool = False) -> None:
    """Run a plain Python REPL."""
    if use_ipython:
        try:
            from IPython import start_ipython  # type: ignore[import-not-found]

            start_ipython()
            return
        except ImportError:
            pass

    import code

    code.interact(banner="Quadkit Python Shell", exitmsg="Goodbye!")


def _run_repl_with_app(use_ipython: bool = False) -> None:
    """Run REPL with app context placeholder.

    Note: Full application bootstrap is not yet implemented.
    """
    out = OutputManager()
    out.print("[yellow]⚠  Full app bootstrap is not yet implemented.[/yellow]")
    out.print()
    out.print("The REPL will start with placeholder objects (all set to None).")
    out.print("For a working app context, run your app manually and connect.")
    out.print()
    out.print(
        "[dim]Alternative: Use 'quadkit shell --no-app' for plain Python REPL[/dim]"
    )
    out.print()

    namespace = {
        "app": None,
        "container": None,
        "config": None,
        "db": None,
        "cache": None,
        "events": None,
    }

    if use_ipython:
        try:
            from IPython import embed

            embed(user_ns=namespace, banner1="")
            return
        except ImportError:
            out.print("[dim]IPython not installed, using standard REPL[/dim]")

    import code

    code.interact(banner="", local=namespace, exitmsg="Goodbye!")


if __name__ == "__main__":
    app()
