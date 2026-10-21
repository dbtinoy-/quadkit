"""quadkit new — scaffold projects and extension packages."""

from __future__ import annotations

from pathlib import Path
import re

import typer

from quadkit.cli.output import OutputManager
from quadkit.cli.scaffold import (
    render_module,
    render_project,
    resolve_template,
    template_names,
)

app = typer.Typer(name="new")


def _valid_name(value: str, kind: str) -> str:
    """Validate a project/package name is a safe Python module slug."""
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", value):
        raise typer.BadParameter(
            f"{kind} name must start with a letter and contain only "
            "letters, digits, dashes, or underscores."
        )
    return value


@app.command("project")
def main(
    name: str = typer.Argument(..., help="Name of the project"),
    template: str = typer.Option(
        "api",
        "--template",
        "-t",
        help=f"Project template (the only template: {', '.join(template_names())})",
    ),
    directory: str = typer.Option(".", "--directory", "-d", help="Target directory"),
    interactive: bool = typer.Option(
        False,
        "--interactive",
        "-i",
        help="Run interactive mode",
    ),
) -> None:
    """Create a new Quadkit project, fully aligned with the framework."""
    out = OutputManager()
    project_name = _valid_name(name, "Project")
    selected_template = template

    names = template_names()
    if interactive and len(names) > 1:
        import click

        selected_template = typer.prompt(
            "Select a template",
            default="api",
            type=click.Choice(names),
        )

    try:
        resolve_template(selected_template)
    except ValueError as exc:
        out.error(str(exc))
        raise typer.Exit(1)

    target_dir = Path(directory) / project_name
    if target_dir.exists() and any(target_dir.iterdir()):
        out.error(f"Directory {target_dir} is not empty.")
        raise typer.Exit(1)

    out.print(
        f"[info]Creating project[/info] [bold]{project_name}[/bold] using "
        f"template [bold]{selected_template}[/bold]...",
    )

    created = render_project(selected_template, project_name, target_dir)

    out.success(f"Project {project_name} created successfully!")
    out.print(
        f"[info]Scaffolded[/info] {len(created)} files "
        f"([bold]{selected_template}[/bold] template).",
    )
    out.print(
        f"\n[bold]Next steps:[/bold]\n"
        f"  cd {project_name}\n"
        f"  pip install -e .\n"
        f"  quadkit gen list\n"
        f"  quadkit dev\n"
        f"  quadkit test",
    )


def _to_class_name(slug: str) -> str:
    """Convert a package slug like 'my-feature' to a PascalCase class name."""
    return "".join(part.capitalize() for part in re.split(r"[-_]", slug))


@app.command("module")
def module(
    name: str = typer.Argument(
        ..., help="Feature name (e.g. 'auth' -> modules/auth/AuthModule)"
    ),
    directory: str = typer.Option(
        ".",
        "--directory",
        "-d",
        help="Project root directory",
    ),
) -> None:
    """Create a bounded context inside a modular project."""
    out = OutputManager()
    module_name = _valid_name(name, "Module")
    try:
        created = render_module(module_name, Path(directory))
    except ValueError as exc:
        out.error(str(exc))
        raise typer.Exit(1)

    class_name = _to_class_name(module_name) + "Module"
    out.success(f"Module {class_name} created successfully! ({len(created)} files)")
    out.print(
        f"\n[bold]Next steps:[/bold]\n"
        f"  quadkit gen controller users --module {module_name}\n"
        f"  quadkit gen service billing --module {module_name}\n"
        f"  quadkit dev",
    )


@app.command("package")
def package(
    name: str = typer.Argument(
        ..., help="Package name (e.g. 'my-feature' → quadkit-my-feature)"
    ),
    description: str = typer.Option(
        "",
        "--description",
        "-d",
        help="Short description for the package",
    ),
    directory: str = typer.Option(".", "--directory", help="Target parent directory"),
) -> None:
    """Scaffold a new quadkit-* extension package.

    Creates quadkit-<name>/ with pyproject.toml, src/ layout, py.typed,
    di/provider.py, and a unit test scaffold.
    """
    out = OutputManager()

    # Normalise: strip leading "quadkit-" if user typed it
    slug = _valid_name(name.removeprefix("quadkit-"), "Package")
    package_name = slug.replace("-", "_")
    full_name = f"quadkit-{slug}"
    class_name = _to_class_name(slug)
    pkg_description = description or f"Quadkit extension package: {full_name}"

    target_dir = Path(directory) / full_name
    if target_dir.exists() and any(target_dir.iterdir()):
        out.error(f"Directory {target_dir} is not empty.")
        raise typer.Exit(1)

    out.print(f"[info]Scaffolding[/info] [bold]{full_name}[/bold]...")

    from quadkit.cli.scaffold_package import render_package

    created = render_package(
        package_name,
        target_dir,
        class_name=class_name,
        description=pkg_description,
    )

    out.success(f"{full_name} scaffolded successfully! ({len(created)} files)")
    out.print(
        f"\n[bold]Next steps:[/bold]\n  cd {full_name}\n  pip install -e .\n  pytest",
    )


__all__ = ["app"]
