"""Project management commands using task runner registry."""

from __future__ import annotations

from typing import Annotated

import typer

from quadkit.cli.lib.console import console
from quadkit.cli.output import OutputManager
from quadkit.cli.registry.task import TaskRunnerRegistry


def _runner_registry() -> TaskRunnerRegistry:
    """Fresh default-populated task runner registry for a command invocation."""
    return TaskRunnerRegistry.with_defaults()


app = typer.Typer()


@app.command()
def test(
    path: str = typer.Argument(".", help="Path to tests"),
    coverage: bool = typer.Option(False, "--coverage", help="Run with coverage"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    runner: str = typer.Option("pytest", "--runner", "-r", help="Test runner to use"),
) -> None:
    """Run project tests."""
    out = OutputManager()

    runner_obj = _runner_registry().get(runner)
    if not runner_obj:
        out.error(f"Unknown test runner: {runner}")
        out.info(
            f"Available runners: {', '.join(r.name for r in _runner_registry().get_all().values())}",
        )
        raise typer.Exit(1)

    if not runner_obj.is_available():
        out.error(f"{runner} not found. Please install it.")
        raise typer.Exit(1)

    out.info(f"Running tests with {runner}...")

    result = runner_obj.run(path=path, coverage=coverage, verbose=verbose)

    console.print(result.output)

    if result.success:
        out.success("Tests passed!")
    else:
        out.error("Tests failed!")
        raise typer.Exit(result.exit_code)


@app.command()
def lint(
    path: str = typer.Argument(".", help="Path to lint"),
    fix: bool = typer.Option(False, "--fix", help="Automatically fix issues"),
    runner: str = typer.Option("ruff", "--runner", "-r", help="Linter to use"),
) -> None:
    """Run project linting."""
    out = OutputManager()

    runner_obj = _runner_registry().get(runner)
    if not runner_obj:
        out.error(f"Unknown linter: {runner}")
        out.info(
            f"Available linters: {', '.join(r.name for r in _runner_registry().get_all().values())}",
        )
        raise typer.Exit(1)

    if not runner_obj.is_available():
        out.error(f"{runner} not found. Please install it.")
        raise typer.Exit(1)

    out.info(f"Running {runner}...")

    result = runner_obj.run(path=path, fix=fix)

    console.print(result.output)

    if result.success:
        out.success("Linting passed!")
    else:
        out.error("Linting found issues.")
        raise typer.Exit(result.exit_code)


@app.command()
def typecheck(
    path: str = typer.Argument("src", help="Path to type check"),
    runner: str = typer.Option("mypy", "--runner", "-r", help="Type checker to use"),
) -> None:
    """Run type checking."""
    out = OutputManager()

    runner_obj = _runner_registry().get(runner)
    if not runner_obj:
        out.error(f"Unknown type checker: {runner}")
        out.info(
            f"Available type checkers: {', '.join(r.name for r in _runner_registry().get_all().values())}",
        )
        raise typer.Exit(1)

    if not runner_obj.is_available():
        out.error(f"{runner} not found. Please install it.")
        raise typer.Exit(1)

    out.info(f"Running {runner}...")

    result = runner_obj.run(path=path)

    console.print(result.output)

    if result.success:
        out.success("Type checking passed!")
    else:
        out.error("Type checking found issues.")
        raise typer.Exit(result.exit_code)


@app.command()
def routes(
    app_path: str = typer.Option(
        None,
        "--app",
        help="Path to the application instance (e.g., myapp.main:app)",
    ),
) -> None:
    """List all registered web and GraphQL routes."""
    out = OutputManager()
    out.print("[yellow]⚠  Route introspection is not yet implemented.[/yellow]")
    out.print()
    out.print("Route introspection requires runtime analysis of your application.")
    out.print("Start your application and use its built-in route listing instead.")


@app.command()
def run_all() -> None:
    """Run all project checks (test, lint, typecheck)."""
    out = OutputManager()

    results: list[tuple[str, bool]] = []

    for runner_name in ["pytest", "ruff", "mypy"]:
        runner = _runner_registry().get(runner_name)
        if runner and runner.is_available():
            out.info(f"Running {runner_name}...")
            result = runner.run()
            results.append((runner_name, result.success))
            if result.success:
                out.success(f"{runner_name} passed!")
            else:
                out.warning(f"{runner_name} found issues!")
        else:
            out.warning(f"{runner_name} not available, skipping")

    all_passed = all(r[1] for r in results)
    if all_passed:
        out.success("All checks passed!")
    else:
        out.error("Some checks failed!")
        raise typer.Exit(1)


@app.command()
def deps(
    outdated: Annotated[
        bool, typer.Option("--outdated", help="Show only outdated packages")
    ] = False,
    tree: Annotated[bool, typer.Option("--tree", help="Show dependency tree")] = False,
) -> None:
    """Show and audit project dependencies.

    Args:
        outdated: Only show outdated packages.
        tree: Show full dependency tree.
    """
    import subprocess

    out = OutputManager()
    cmd = ["uv", "tree"] if tree else ["uv", "pip", "list"]
    if outdated and not tree:
        cmd += ["--outdated"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)  # noqa: S603
        if result.returncode != 0:
            out.print(f"[red]{result.stderr.strip()}[/red]")
            raise typer.Exit(result.returncode)
        out.print(result.stdout)
    except FileNotFoundError:
        out.print("[red]uv not found. Install uv to use this command.[/red]")
        raise typer.Exit(1)


__all__ = ["app"]
