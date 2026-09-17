"""Quadkit CLI entry point.

Commands resolve lazily (plans/09172026 C-01..C-04): importing this module
must not import any command module, the CLI-context chain, or run the
contributor entry-point scan. Only the command actually invoked pays its
own import cost — ``quadkit version`` imports the version command and
nothing else.
"""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import Annotated, Any

import click
import typer
from typer.core import TyperGroup

# ---------------------------------------------------------------------------
# Static command table (C-01)
# ---------------------------------------------------------------------------
# name -> (module, attribute, help). Typer groups expose ``app``; the meta
# leaves are plain functions. Plain data so ``--help``, shell completion and
# name resolution never import command modules.

_COMMAND_TABLE: dict[str, tuple[str, str, str]] = {
    "init": (
        "quadkit.cli.commands.init",
        "app",
        "Initialize Quadkit in existing project",
    ),
    "new": (
        "quadkit.cli.commands.new",
        "app",
        "Create a new Quadkit project",
    ),
    "add": (
        "quadkit.cli.commands.add",
        "app",
        "Add a provider to the project",
    ),
    "dev": (
        "quadkit.cli.commands.dev",
        "app",
        "Development server and tools",
    ),
    "run": (
        "quadkit.cli.commands.run",
        "app",
        "Smart runner — auto-detects factory, sets profile",
    ),
    "db": ("quadkit.cli.commands.db", "app", "Database management commands"),
    "events": (
        "quadkit.cli.commands.events",
        "app",
        "Event schema management commands",
    ),
    "gen": ("quadkit.cli.commands.gen", "app", "Code generation commands"),
    "config": (
        "quadkit.cli.commands.config",
        "app",
        "Configuration management",
    ),
    "inspect": (
        "quadkit.cli.commands.inspect",
        "app",
        "Inspect runtime state",
    ),
    "shell": (
        "quadkit.cli.commands.shell",
        "app",
        "Interactive Python REPL",
    ),
    "contrib": (
        "quadkit.cli.commands.contrib",
        "app",
        "Discover and inspect installed contributors",
    ),
    "project": (
        "quadkit.cli.commands.project",
        "app",
        "Project management (test, lint, routes)",
    ),
    "system": (
        "quadkit.cli.commands.system",
        "app",
        "System information and management",
    ),
    # Leaf commands live in commands/meta.py as plain functions.
    "version": (
        "quadkit.cli.commands.meta",
        "version",
        "Show framework and package versions.",
    ),
    "completion": (
        "quadkit.cli.commands.meta",
        "completion",
        "Generate shell completion script.",
    ),
    "list": (
        "quadkit.cli.commands.meta",
        "list_commands",
        "List all available commands.",
    ),
    "test": (
        "quadkit.cli.commands.meta",
        "test",
        "Run project tests.",
    ),
    "lint": (
        "quadkit.cli.commands.meta",
        "lint",
        "Run project linting.",
    ),
}

# Reserved command names (groups above plus names contributed by the
# installed Quadkit distributions). Contributor registration skips these.
_BUILTIN_COMMANDS: frozenset[str] = frozenset(_COMMAND_TABLE) | {
    "health",
    "doctor",
}


class _LazyBuiltinCommand(TyperGroup):
    """Stand-in for a built-in command that materializes it on first use.

    Listing contexts — root ``--help``, shell completion, error suggestions
    — only touch the lightweight attributes served from the static table
    (``name``/``help``/``short_help``/``hidden``/``deprecated``). Parsing,
    invocation, or dedicated help resolves through to the real Typer-backed
    command, importing its module exactly once and only when actually used.
    """

    _LIGHT_ATTRS = frozenset(
        {
            "name",
            "help",
            "short_help",
            "hidden",
            "deprecated",
            "epilog",
            "rich_help_panel",
        }
    )

    def __init__(
        self,
        *,
        name: str,
        module_path: str,
        attr: str,
        help_text: str,
    ) -> None:
        super().__init__(name=name, help=help_text)
        self._lazy_spec = (module_path, attr, help_text)
        self._lazy_real: click.Command | None = None

    def _materialize(self) -> click.Command:
        real = self._lazy_real
        if real is None:
            module_path, attr, help_text = self._lazy_spec
            module = import_module(module_path)
            obj = getattr(module, attr)
            if isinstance(obj, typer.Typer):
                # get_group (not get_command): add_typer always nests a
                # group, and get_command collapses single-command Tylers
                # into bare commands — which would break subcommand
                # dispatch for those apps.
                real = typer.main.get_group(obj)
            else:
                # Leaf function: register it on a one-command Typer so
                # Annotated typer options keep their processing.
                sub = typer.Typer()
                sub.command(name=self.name)(obj)
                real = typer.main.get_command(sub)
            real.name = self.name
            if help_text:
                real.help = help_text
            self._lazy_real = real
        return real

    def __getattribute__(self, name: str) -> Any:
        # Lightweight listing attributes (and privates/dunders) are served
        # from the stub; anything else defers to the materialized command.
        if name in _LazyBuiltinCommand._LIGHT_ATTRS or name.startswith("_"):
            return object.__getattribute__(self, name)
        real = object.__getattribute__(self, "_materialize")()
        return getattr(real, name)


class _ContributedCapture:
    """Duck-typed Typer app that captures contributed commands.

    ``ContributorRuntime.register_commands`` registers sub-apps via
    ``app.add_typer(...)``; this shim converts each one to a click command
    and stores it for the lazy group instead.
    """

    def __init__(self, store: dict[str, click.Command]) -> None:
        self._store = store

    def add_typer(self, sub_app: Any, name: str | None = None, **kwargs: Any) -> None:
        if not name:
            return
        # get_group mirrors add_typer's nesting for single-command Tylers.
        command = typer.main.get_group(sub_app)
        command.name = name
        help_text = kwargs.get("help")
        if help_text is not None:
            command.help = help_text
        self._store[name] = command


class LazyQuadkitGroup(TyperGroup):
    """Root group that resolves Quadkit commands on demand.

    Built-in commands come from the static table as
    :class:`_LazyBuiltinCommand` stubs; contributed commands load via the
    entry-point scan on first miss and are memoized.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._contributed: dict[str, click.Command] = {}
        self._contributed_loaded = False

    def get_command(self, ctx: click.Context, cmd_name: str) -> click.Command | None:
        command = self.commands.get(cmd_name)
        if command is not None:
            return command
        entry = _COMMAND_TABLE.get(cmd_name)
        if entry is not None:
            module_path, attr, help_text = entry
            command = _LazyBuiltinCommand(
                name=cmd_name,
                module_path=module_path,
                attr=attr,
                help_text=help_text,
            )
            self.commands[cmd_name] = command
            return command
        self._ensure_contributed()
        return self._contributed.get(cmd_name)

    def list_commands(self, ctx: click.Context) -> list[str]:
        self._ensure_contributed()
        return sorted(set(_COMMAND_TABLE) | set(self._contributed))

    def _ensure_contributed(self) -> None:
        """Run the contributor entry-point scan once, on demand (C-04)."""
        if self._contributed_loaded:
            return
        self._contributed_loaded = True
        try:
            from quadkit.cli.contributors.runtime import ContributorRuntime

            capture = _ContributedCapture(self._contributed)
            ContributorRuntime.from_entry_points().register_commands(
                capture, _BUILTIN_COMMANDS
            )
        except Exception as exc:  # noqa: BLE001 — a failed scan must not break the CLI
            import sys

            print(f"warning: contributor scan failed: {exc}", file=sys.stderr)


app = typer.Typer(
    name="quadkit",
    help="Quadkit Framework CLI — build, run, and manage Quadkit applications.",
    add_completion=True,
    invoke_without_command=True,
    rich_markup_mode="rich",
    cls=LazyQuadkitGroup,
)


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
    # Deferred (C-03): importing the CLI context chain at module scope
    # costs ~160 ms on every invocation; only invocations that reach here
    # need it.
    from quadkit.cli.runtime import CLIContext

    ctx.obj["cli_context"] = CLIContext(
        json_mode=json_output,
        quiet=quiet,
        debug=debug,
        no_color=no_color,
        config_path=config_path,
    )


if __name__ == "__main__":
    app()
