from __future__ import annotations

from collections.abc import Callable
import importlib.metadata
from typing import Annotated

import typer

from quadkit.cli.constants import __version__
from quadkit.cli.output import OutputManager
from quadkit.cli.package_names import installed_quadkit_distributions
from quadkit.cli.registry.command import CommandEntry, CommandRegistry


def _build_command_registry() -> CommandRegistry:
    from quadkit.cli.contributors.runtime import ContributorRuntime  # noqa: PLC0415

    registry = CommandRegistry()

    builtins: list[CommandEntry] = [
        CommandEntry(
            "init", "Initialize Quadkit in existing project", "Project", "builtin"
        ),
        CommandEntry("new", "Create a new Quadkit project", "Project", "builtin"),
        CommandEntry("add", "Add a provider to the project", "Project", "builtin"),
        CommandEntry("dev", "Development server and tools", "Server", "builtin"),
        CommandEntry(
            "run",
            "Smart runner — auto-detects factory, sets profile",
            "Server",
            "builtin",
        ),
        CommandEntry("db", "Database management commands", "Database", "builtin"),
        CommandEntry("events", "Event schema management commands", "Events", "builtin"),
        CommandEntry("gen", "Code generation commands", "Code Generation", "builtin"),
        CommandEntry("config", "Configuration management", "Configuration", "builtin"),
        CommandEntry("inspect", "Inspect runtime state", "Inspection", "builtin"),
        CommandEntry("shell", "Interactive Python REPL", "System", "builtin"),
        CommandEntry(
            "contrib",
            "Discover and inspect installed contributors",
            "Plugins",
            "builtin",
        ),
        CommandEntry(
            "project", "Project management (test, lint, routes)", "Testing", "builtin"
        ),
        CommandEntry(
            "system", "System information and management", "System", "builtin"
        ),
        CommandEntry(
            "version", "Show framework and package versions", "Utilities", "builtin"
        ),
        CommandEntry(
            "completion", "Generate shell completion script", "Utilities", "builtin"
        ),
        CommandEntry("list", "List all available commands", "Utilities", "builtin"),
        CommandEntry("test", "Run project tests", "Testing", "builtin"),
        CommandEntry("lint", "Run project linting", "Testing", "builtin"),
    ]
    for entry in builtins:
        registry.register(entry)

    runtime = ContributorRuntime.from_entry_points()
    for cmd in runtime.commands:
        if cmd.name not in registry.entries:
            registry.register(
                CommandEntry(
                    name=cmd.name,
                    help=cmd.help or "",
                    category=cmd.category or "Extensions",
                    source=cmd.contributor,
                    hidden=cmd.hidden or False,
                )
            )

    return registry


def version(
    all_packages: Annotated[
        bool,
        typer.Option("--all", help="Show all package versions"),
    ] = False,
) -> None:
    """Show framework and package versions."""
    out = OutputManager()
    out.print(f"quadkit {__version__}")
    if all_packages:
        packages = installed_quadkit_distributions()
        rows = []
        for pkg in packages:
            try:
                ver = importlib.metadata.version(pkg)
            except importlib.metadata.PackageNotFoundError:
                ver = "not installed"
            rows.append([pkg, ver])
        out.table(["Package", "Version"], rows)


def _bash_completion(registry: CommandRegistry) -> str:
    """Render the bash completion script."""
    words = " ".join(registry.names())
    return f"""# Quadkit CLI Bash Completion
_quadkit_complete() {{
    local cur prev
    COMPREPLY=()
    cur="${{COMP_WORDS[COMP_CWORD]}}"
    prev="${{COMP_WORDS[COMP_CWORD-1]}}"

    case ${{prev}} in
        quadkit)
            COMPREPLY=( $(compgen -W "{words}" -- ${{cur}}) )
            ;;
        *)
            ;;
    esac

    return 0
}}
complete -F _quadkit_complete quadkit
"""


def _zsh_completion(registry: CommandRegistry) -> str:
    """Render the zsh completion script."""
    commands_block = "\n".join(
        f"        '{e.name}:{e.help}'" for e in registry.all_entries()
    )
    return f"""# Quadkit CLI Zsh Completion
autoload -U compinit
compdef _quadkit quadkit

_quadkit() {{
    local -a commands
    commands=(
{commands_block}
    )

    _describe 'command' commands
}}

_quadkit
"""


def _fish_completion(registry: CommandRegistry) -> str:
    """Render the fish completion script."""
    words = " ".join(registry.names())
    return f"""# Quadkit CLI Fish Completion
complete -c quadkit -f -a '{words}'
"""


def _powershell_completion(registry: CommandRegistry) -> str:
    """Render the PowerShell completion script."""
    names_ps = ", ".join(f"'{n}'" for n in registry.names())
    return f"""# Quadkit CLI PowerShell Completion
$completions = @(
    {names_ps}
)

Register-ArgumentCompleter -CommandName quadkit -ParameterName Command -ScriptBlock {{
    param($wordToComplete, $commandDetails, $cursorPosition)
    $completions | Where-Object {{ $_ -like "$wordToComplete*" }} | ForEach-Object {{
        [System.Management.Automation.CompletionResult]::new($_, $_, 'ParameterValue', $_)
    }}
}}
"""


#: Shell name → completion-script builder (registry dispatch, no branch chain).
_COMPLETION_SCRIPTS: dict[str, Callable[[CommandRegistry], str]] = {
    "bash": _bash_completion,
    "zsh": _zsh_completion,
    "fish": _fish_completion,
    "powershell": _powershell_completion,
}

#: Shell name → the line a user adds to their shell profile.
_COMPLETION_INSTALL_HINTS: dict[str, str] = {
    "bash": '  eval "$(quadkit completion --shell bash)"',
    "zsh": '  eval "$(quadkit completion --shell zsh)"',
    "fish": "  quadkit completion --shell fish >> ~/.config/fish/completions/quadkit.fish",
    "powershell": "  quadkit completion --shell powershell >> $PROFILE",
}


def completion(
    shell: Annotated[
        str,
        typer.Option("--shell", help="Shell type (bash, zsh, fish, powershell)"),
    ] = "bash",
) -> None:
    """Generate shell completion script."""
    out = OutputManager()

    builder = _COMPLETION_SCRIPTS.get(shell)
    if builder is None:
        out.error(f"Unsupported shell: {shell}")
        raise typer.Exit(1)

    out.print(builder(_build_command_registry()))
    out.print()
    out.print("[dim]To install, add to your shell config:[/dim]")
    out.print(_COMPLETION_INSTALL_HINTS[shell])


def list_commands(
    group: Annotated[
        str | None,
        typer.Option("--group", "-g", help="Filter by command group"),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output in JSON format"),
    ] = False,
) -> None:
    """List all available commands."""
    out = OutputManager()

    registry = _build_command_registry()

    if json_output:
        payload = {
            "commands": [
                {
                    "name": e.name,
                    "help": e.help,
                    "category": e.category,
                    "source": e.source,
                    "hidden": e.hidden,
                }
                for e in registry.all_entries()
            ],
        }
        from quadkit.serialization import dumps_str

        out.print(dumps_str(payload))
        return

    if group:
        groups = registry.by_category()
        cmds = groups.get(group)
        if cmds:
            out.print(f"[bold]{group}:[/bold]")
            for cmd in cmds:
                out.print(f"  quadkit {cmd.name}")
        else:
            out.error(f"Unknown group: {group}")
            out.print(f"Available: {', '.join(groups.keys())}")
        return

    out.print("[bold]Available Commands:[/bold]\n")
    for group_name, commands in registry.by_category().items():
        out.print(f"[bold]{group_name}:[/bold]")
        for cmd in commands:
            out.print(f"  quadkit {cmd.name}")
        out.print()

    out.print("[dim]Use 'quadkit <command> --help' for more info.[/dim]")


def test(
    path: str = typer.Argument(".", help="Path to tests"),
    coverage: bool = typer.Option(False, "--coverage", help="Run with coverage"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
) -> None:
    """Run project tests."""
    from quadkit.cli.commands.project import test as project_test

    project_test(path=path, coverage=coverage, verbose=verbose)


def lint(
    path: str = typer.Argument(".", help="Path to lint"),
    fix: bool = typer.Option(False, "--fix", help="Auto-fix issues"),
    check: bool = typer.Option(False, "--check", help="Check only, no changes"),
) -> None:
    """Run project linting."""
    from quadkit.cli.commands.project import lint as project_lint

    project_lint(path=path, fix=fix)


__all__ = [
    "completion",
    "lint",
    "list_commands",
    "test",
    "version",
]
