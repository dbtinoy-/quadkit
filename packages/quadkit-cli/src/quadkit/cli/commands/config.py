"""Commands for managing Quadkit configuration."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import os
from pathlib import Path
import re
from typing import Annotated, Any

import aiofiles
import typer
import yaml

from quadkit.cli.commands.config_utils import (
    _dict_diff as _dict_diff,
)
from quadkit.cli.commands.config_utils import (
    _mask_secrets as _mask_secrets,
)
from quadkit.cli.exceptions import ConfigNotFoundError
from quadkit.cli.lib import find_config, load_config_yaml_async, save_config_yaml_async
from quadkit.cli.output import OutputManager
from quadkit.cli.registry.config import (
    has_errors,
    validate_config,
)
from quadkit.cli.runtime import handle_errors
from quadkit.contracts.constants import DOCS_BASE_URL
from quadkit.contracts.exceptions.domain import ValidationError

app = typer.Typer()


def _write_config_yaml(out: OutputManager, data: dict[str, Any]) -> None:
    """Print the config as YAML."""
    out.print(yaml.dump(data, sort_keys=False))


def _write_config_json(out: OutputManager, data: dict[str, Any]) -> None:
    """Print the config as JSON."""
    from quadkit import serialization as json

    out.print(json.dumps(data, indent=2))


def _write_config_table(out: OutputManager, data: dict[str, Any]) -> None:
    """Print the config as a two-column table."""
    out.table(["Key", "Value"], [[k, str(v)] for k, v in data.items()])


#: `--format` value → writer (registry dispatch, no branch chain).
_CONFIG_WRITERS: dict[str, Callable[[OutputManager, dict[str, Any]], None]] = {
    "yaml": _write_config_yaml,
    "json": _write_config_json,
    "table": _write_config_table,
}


@app.command()
@handle_errors
def show(
    reveal_secrets: Annotated[
        bool,
        typer.Option("--reveal-secrets", help="Show secret values"),
    ] = False,
    file_format: Annotated[
        str,
        typer.Option("--format", "-f", help="Output format (yaml, json, table)"),
    ] = "yaml",
) -> None:
    """Show current configuration."""
    out = OutputManager()

    async def _run() -> None:
        try:
            config_path = find_config()
            config_data = await load_config_yaml_async(config_path)
        except (ConfigNotFoundError, FileNotFoundError):
            # Both are reachable here: find_config() raises the former, and
            # the try also wraps the read, which can lose the file to a
            # race after the walk.
            out.error(
                "No application.yaml found in current directory or any parent.",
                hint="Run `quadkit init` to create one.",
            )
            raise typer.Exit(1) from None

        masked_config = _mask_secrets(config_data, reveal=reveal_secrets)

        writer = _CONFIG_WRITERS.get(file_format)
        if writer is None:
            out.error(
                f"Unsupported format: {file_format}",
                hint=f"Use one of: {', '.join(sorted(_CONFIG_WRITERS))}",
            )
            raise typer.Exit(1)

        writer(out, masked_config)

    asyncio.run(_run())


@app.command()
@handle_errors
def init(
    output: str = typer.Option(
        "application.yaml",
        "--output",
        "-o",
        help="Path to create the configuration file",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Overwrite existing file if it exists",
    ),
) -> None:
    """Initialize a new Quadkit configuration file with default settings."""
    out = OutputManager()
    path = Path(output)

    if path.exists() and not force:
        out.error(
            f"Configuration file already exists: {output}.",
            hint="Use --force to overwrite.",
        )
        raise typer.Exit(1)

    default_config = {
        "project": {
            "name": "my-quadkit-project",
            "version": "0.1.0",
        },
        "logging": {
            "level": "INFO",
            "format": "json",
        },
        "features": {
            "ai": {"enabled": True},
            "graphql": {"enabled": True},
            "auth": {"enabled": False},
        },
    }

    async def _run() -> None:
        try:
            await save_config_yaml_async(
                path,
                default_config,
                header=(
                    "# Quadkit Framework Configuration\n"
                    f"# Documented at {DOCS_BASE_URL}/config\n\n"
                ),
            )

            out.success(f"Created configuration file: {output}")
            out.info("Run 'quadkit config validate' to check your configuration.")
        except OSError as error:
            out.error(f"Failed to create configuration file: {error}")
            raise typer.Exit(1) from None

    asyncio.run(_run())


@app.command()
@handle_errors
def validate(
    file: str = typer.Option(
        "application.yaml",
        "--file",
        "-f",
        help="Configuration file to validate",
    ),
) -> None:
    """Validate configuration file."""
    out = OutputManager()

    async def _run() -> None:
        path = Path(file)
        if not path.exists():
            out.error(f"Configuration file not found: {file}")
            raise typer.Exit(1)

        try:
            from quadkit.config import QuadkitConfig

            data = await load_config_yaml_async(path)

            if not data:
                out.error("Configuration file is empty.")
                raise typer.Exit(1)

            QuadkitConfig(**data)

            results = validate_config(data)
            if has_errors(results):
                out.error("Configuration validation failed")
                for issues in results.values():
                    for issue in issues:
                        if issue.severity == "error":
                            out.error(issue.message)
                raise typer.Exit(1)

            out.success("Configuration is valid!")

        except ValidationError as e:
            out.error("Configuration validation failed")
            rows = [[err.field, err.message] for err in e.errors]
            out.table(["Field", "Error"], rows)
            raise typer.Exit(1) from None
        except Exception as e:  # noqa: BLE001 — any validation failure is a CLI error
            out.error(f"Configuration validation failed: {e}")
            raise typer.Exit(1) from None

    asyncio.run(_run())


@app.command()
@handle_errors
def schema(
    output: str = typer.Option(
        "quadkit-schema.json",
        "--output",
        "-o",
        help="Output file",
    ),
) -> None:
    """Export configuration JSON schema."""
    out = OutputManager()
    out.info(f"Exporting configuration schema: {output}")

    async def _run() -> None:
        try:
            from quadkit import serialization as json
            from quadkit.config import QuadkitConfig

            schema = QuadkitConfig.model_json_schema()
            content = json.dumps(schema, indent=2).decode("utf-8")
            async with aiofiles.open(output, "w") as file_handle:
                await file_handle.write(content)

            out.success(f"Configuration schema exported to {output}")
        except Exception as error:  # noqa: BLE001 — any export failure is a CLI error
            out.error(f"Failed to export schema: {error}")
            raise typer.Exit(1) from None

    asyncio.run(_run())


@app.command()
@handle_errors
def doctor(
    fix: bool = typer.Option(
        False,
        "--fix",
        help="Attempt to fix issues automatically",
    ),
    env: str = typer.Option(
        "development",
        "--env",
        "-e",
        help="Environment to validate",
    ),
) -> None:
    """Diagnose configuration issues."""
    out = OutputManager()

    async def _run() -> None:
        config_path = Path("application.yaml")
        if not config_path.exists():
            out.error("Configuration file not found")
            out.info("Run 'quadkit init' to create one")
            raise typer.Exit(1)

        out.info("Running configuration diagnostics...")

        try:
            await load_config_yaml_async(config_path)
        except yaml.YAMLError as e:
            out.error(f"Invalid YAML: {e}")
            raise typer.Exit(1) from None

        config_data = await load_config_yaml_async(config_path)

        results = validate_config(config_data, env)

        total_errors = 0
        total_warnings = 0
        total_infos = 0

        for validator_name, issues in results.items():
            if not issues:
                continue

            out.print(f"\n[bold]{validator_name}[/bold]")
            for issue in issues:
                if issue.severity == "error":
                    total_errors += 1
                    out.print(f"  [red]✗[/red] {issue.message}")
                    if issue.suggestion:
                        out.print(f"      [dim]Hint: {issue.suggestion}[/dim]")
                elif issue.severity == "warning":
                    total_warnings += 1
                    out.print(f"  [yellow]⚠[/yellow] {issue.message}")
                    if issue.suggestion:
                        out.print(f"      [dim]Hint: {issue.suggestion}[/dim]")
                else:
                    total_infos += 1
                    out.print(f"  [info]i[/info] {issue.message}")

        out.print("\n[bold]Summary[/bold]")
        summary_parts = []
        if total_errors:
            summary_parts.append(f"[red]{total_errors} errors[/red]")
        if total_warnings:
            summary_parts.append(f"[yellow]{total_warnings} warnings[/yellow]")
        if total_infos:
            summary_parts.append(f"[info]{total_infos} info[/info]")

        if not summary_parts:
            out.success("Configuration is healthy!")
        else:
            out.print("  " + ", ".join(summary_parts))

        if has_errors(results):
            raise typer.Exit(1)

    asyncio.run(_run())


@app.command("env")
@handle_errors
def env_cmd(
    missing: bool = typer.Option(
        False,
        "--missing",
        help="Show only missing environment variables",
    ),
) -> None:
    """Show environment variables used in configuration."""
    out = OutputManager()

    async def _run() -> None:
        try:
            config_path = find_config()
        except ConfigNotFoundError:
            # find_config() raises ConfigNotFoundError (a CliError), never
            # FileNotFoundError: it walks candidates with ``.is_file()``. The
            # old arm therefore never ran, and this message never printed.
            out.error("No application.yaml found")
            raise typer.Exit(1) from None

        env_vars: dict[str, str] = {}

        async with aiofiles.open(config_path) as f:
            raw_content = await f.read()

        matches = re.findall(r"\$\{([^}:]+)(?::[^}]*)?\}", raw_content)
        for var in set(matches):
            env_vars[var] = os.environ.get(var, "<not set>")

        if not env_vars:
            out.info("No environment variables found in configuration")
            return

        if missing:
            missing_vars = {k: v for k, v in env_vars.items() if v == "<not set>"}
            if not missing_vars:
                out.success("All required environment variables are set")
                return
            out.print("[bold]Missing environment variables:[/bold]")
            for var, value in missing_vars.items():
                out.print(f"  {var}: {value}")
            raise typer.Exit(1)

        out.print("[bold]Environment variables in configuration:[/bold]")
        for var, value in env_vars.items():
            display_value = value if value != "<not set>" else "[red]<not set>[/red]"
            out.print(f"  {var}: {display_value}")

    asyncio.run(_run())


@app.command()
@handle_errors
def diff(
    baseline: str = typer.Option(
        "application.yaml",
        "--baseline",
        "-b",
        help="Baseline config file",
    ),
    compare: str = typer.Option(
        ...,
        "--compare",
        "-c",
        help="Config file to compare against the baseline",
    ),
) -> None:
    """Show the difference between two configuration files."""
    out = OutputManager()

    async def _run() -> None:
        baseline_path = Path(baseline)
        compare_path = Path(compare)

        if not baseline_path.exists():
            out.error(f"Baseline file not found: {baseline}")
            raise typer.Exit(1)
        if not compare_path.exists():
            out.error(f"Compare file not found: {compare}")
            raise typer.Exit(1)

        base_data = await load_config_yaml_async(baseline_path)
        cmp_data = await load_config_yaml_async(compare_path)

        added, removed, changed = _dict_diff(base_data, cmp_data)

        if not added and not removed and not changed:
            out.success("Files are identical")
            return

        if added:
            out.print("\n[bold green]Added keys:[/bold green]")
            for key in sorted(added):
                out.print(f"  [green]+[/green] {key}: {added[key]}")
        if removed:
            out.print("\n[bold red]Removed keys:[/bold red]")
            for key in sorted(removed):
                out.print(f"  [red]-[/red] {key}: {removed[key]}")
        if changed:
            out.print("\n[bold yellow]Changed keys:[/bold yellow]")
            for key in sorted(changed):
                old_val, new_val = changed[key]
                out.print(f"  [yellow]~[/yellow] {key}: {old_val!r} → {new_val!r}")

    asyncio.run(_run())


@app.command("env-example")
@handle_errors
def env_example(
    output: str = typer.Option(
        ".env.example",
        "--output",
        "-o",
        help="Output file for the generated .env example",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Overwrite existing file if it exists",
    ),
) -> None:
    """Generate a .env.example file from the current configuration.

    Extracts all ``${VAR}`` and ``${VAR:default}`` references from the config
    YAML and writes them as ``VAR=<value-or-placeholder>`` lines.
    """
    out = OutputManager()

    async def _run() -> None:
        try:
            config_path = find_config()
        except ConfigNotFoundError:
            # find_config() raises ConfigNotFoundError (a CliError), never
            # FileNotFoundError: it walks candidates with ``.is_file()``. The
            # old arm therefore never ran, and this message never printed.
            out.error("No application.yaml found")
            raise typer.Exit(1) from None

        output_path = Path(output)
        if output_path.exists() and not force:
            out.error(
                f"{output} already exists.",
                hint="Use --force to overwrite.",
            )
            raise typer.Exit(1)

        async with aiofiles.open(config_path) as f:
            raw_content = await f.read()
        # Collect VAR and optional inline default from ${VAR:default} syntax
        matches = re.findall(r"\$\{([^}:]+)(?::([^}]*))?\}", raw_content)

        seen: dict[str, str] = {}
        for var, default in matches:
            if var not in seen:
                seen[var] = default or os.environ.get(var, "")

        if not seen:
            out.info("No environment variable references found in configuration")
            return

        lines = ["# Auto-generated .env.example — review before committing\n"]
        for var in sorted(seen):
            placeholder = seen[var] if seen[var] else f"<{var.lower()}>"
            lines.append(f"{var}={placeholder}\n")

        async with aiofiles.open(output_path, "w") as f:
            await f.write("".join(lines))
        out.success(f"Generated {output} with {len(seen)} variable(s)")

    asyncio.run(_run())


__all__ = ["app"]
