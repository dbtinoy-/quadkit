from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import Any

import typer
import yaml

from quadkit.cli.output import OutputManager
from quadkit.cli.package_names import installed_quadkit_distributions
from quadkit.cli.registry.health import (
    CheckResult,
    CheckStatus,
    run_health_checks,
)

app = typer.Typer()


def _resolve_callable(path: str) -> Any:
    module_path, _, attr_path = path.partition(":")
    if not module_path or not attr_path:
        raise ValueError(f"Invalid path: {path}")
    module = import_module(module_path)
    resolved: Any = module
    for part in attr_path.split("."):
        resolved = getattr(resolved, part)
    return resolved


@app.command()
def info() -> None:
    """Display information about the Quadkit environment."""
    out = OutputManager()
    out.print("[bold cyan]Quadkit Environment Info[/bold cyan]")
    import platform
    import sys

    out.print(f"Python Version: {sys.version.split()[0]}")
    out.print(f"Platform: {platform.platform()}")
    out.print("Framework Version: 0.1.0")

    config_path = Path("application.yaml")
    if config_path.exists():
        out.print(f"Project Config: [success]{config_path.absolute()}[/success]")
    else:
        out.print("Project Config: [warning]Not found[/warning]")

    out.print("\n[bold]Core Packages:[/bold]")
    for pkg in installed_quadkit_distributions():
        out.print(f"- {pkg}")


@app.command()
def health(
    strict: bool = typer.Option(
        False,
        "--strict",
        help="Fail on non-critical issues too",
    ),
) -> None:
    """Check the health of the current Quadkit project."""
    out = OutputManager()
    from quadkit.cli.contributors.runtime import ContributorRuntime  # noqa: PLC0415

    out.print("[info]Checking Quadkit project health...[/info]")

    results: list[CheckResult] = []

    project_checks = [
        ("application.yaml exists", Path("application.yaml").exists()),
        ("pyproject.toml exists", Path("pyproject.toml").exists()),
        ("src directory exists", Path("src").exists()),
    ]
    for label, passed in project_checks:
        status = CheckStatus.PASS if passed else CheckStatus.FAIL
        results.append(CheckResult(name=label, status=status, message=label))
        icon = "[success]✓[/success]" if passed else "[error]✗[/error]"
        out.print(f"{icon} {label}")

    runtime = ContributorRuntime.from_entry_points()
    for check in runtime.health_checks:
        try:
            fn = _resolve_callable(check.check_path)
            result: CheckResult = fn()
            results.append(result)
            icon = result.icon
            color = result.color
            out.print(
                f"  [{color}]{icon}[/{color}] [{color}]{check.name}[/{color}]"
                f"  {result.message}"
            )
        except Exception as exc:
            results.append(
                CheckResult(
                    name=check.name,
                    status=CheckStatus.FAIL,
                    message=str(exc),
                )
            )
            out.print(f"  [red]✗[/red] {check.name}: {exc}")

    failures = [r for r in results if r.status == CheckStatus.FAIL]
    if strict:
        failures = [
            r for r in results if r.status in (CheckStatus.FAIL, CheckStatus.WARNING)
        ]
    if failures:
        raise typer.Exit(1)


@app.command()
def shell() -> None:
    """Open an interactive Quadkit shell."""
    out = OutputManager()
    out.print("[info]Opening Quadkit interactive shell...[/info]")
    try:
        import IPython  # type: ignore[import-not-found]

        IPython.embed(header="Quadkit Shell - DI Container available as 'container'")
    except ImportError:
        import code

        code.interact(local=locals())


@app.command()
def providers() -> None:
    """List all registered providers in the current project."""
    out = OutputManager()
    out.print("[bold cyan]Registered Providers:[/bold cyan]")

    config_path = Path("application.yaml")
    if config_path.exists():
        try:
            with open(config_path) as f:
                config = yaml.safe_load(f) or {}

            for key in config:
                if key in [
                    "database",
                    "auth",
                    "ai",
                    "cache",
                    "messaging",
                    "events",
                    "search",
                    "storage",
                    "monitor",
                    "tasks",
                    "graphql",
                ]:
                    out.print(f"- [success]{key}[/success]")
        except Exception as e:  # noqa: BLE001 — any parse failure is a CLI error
            out.print(f"[error]Failed to parse application.yaml: {e}[/error]")
    else:
        out.print(
            "[warning]application.yaml not found. Showing default core providers.[/warning]",
        )
        out.print("- common")
        out.print("- cli")


@app.command()
def doctor(
    fix: bool = typer.Option(
        False,
        "--fix",
        help="Attempt to fix issues automatically",
    ),
) -> None:
    """Diagnose system environment and configuration issues."""
    out = OutputManager()
    from quadkit.cli.contributors.runtime import ContributorRuntime  # noqa: PLC0415

    out.print("[bold cyan]Running system diagnostics...[/bold cyan]\n")

    results: list[CheckResult] = []

    runtime_results = run_health_checks()
    for category, checks in runtime_results.items():
        out.print(f"[bold]{category}[/bold]")
        for result in checks:
            results.append(result)
            icon = result.icon
            color = result.color
            out.print(f"  [{color}]{icon}[/{color}] {result.message}")
        out.print()

    runtime = ContributorRuntime.from_entry_points()
    for check in runtime.doctor_checks:
        try:
            fn = _resolve_callable(check.check_path)
            check_result = fn()
            results.append(check_result)
            icon = check_result.icon
            color = check_result.color
            out.print(
                f"  [{color}]{icon}[/{color}] [{color}]{check.name}[/{color}]"
                f"  {result.message}"
            )
        except Exception as exc:
            results.append(
                CheckResult(
                    name=check.name,
                    status=CheckStatus.FAIL,
                    message=str(exc),
                )
            )
            out.print(f"  [red]✗[/red] {check.name}: {exc}")

    out.print()
    total_pass = sum(1 for r in results if r.status == CheckStatus.PASS)
    total_warning = sum(1 for r in results if r.status == CheckStatus.WARNING)
    total_fail = sum(1 for r in results if r.status == CheckStatus.FAIL)
    total_skip = sum(1 for r in results if r.status == CheckStatus.SKIP)

    out.print("[bold]Summary[/bold]")
    summary_parts = []
    if total_pass:
        summary_parts.append(f"[success]{total_pass} passed[/success]")
    if total_warning:
        summary_parts.append(f"[yellow]{total_warning} warnings[/yellow]")
    if total_fail:
        summary_parts.append(f"[red]{total_fail} failed[/red]")
    if total_skip:
        summary_parts.append(f"[dim]{total_skip} skipped[/dim]")
    if summary_parts:
        out.print("  " + ", ".join(summary_parts))
    else:
        out.print("  [success]All checks passed![/success]")

    if fix and total_fail > 0:
        out.print("\n[bold]Attempting fixes...[/bold]")
        if total_warning > 0:
            out.print("[info]Run 'uv sync' to install dependencies[/info]")
        if not Path("application.yaml").exists():
            out.print("[info]Run 'quadkit init' to create configuration[/info]")

    if total_fail > 0:
        raise typer.Exit(1)


__all__ = ["app"]
