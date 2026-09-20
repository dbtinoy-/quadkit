"""CommandAssembler: wires CliContributorRegistry generators onto a Typer app."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from quadkit.cli.contributors.registry import CliContributorRegistry
from quadkit.cli.output import OutputManager
from quadkit.cli.registry.generator import GeneratorRegistry
from quadkit.cli.runtime import handle_errors
from quadkit.contracts.cli.types import GeneratorDefinition


def _resolve_default_output(
    default: str,
    generator: str,
    module: str | None,
) -> str:
    """Resolve a generator default against the project it is run in.

    Falls back to sniffing ``src/`` when the project declares no
    ``[tool.quadkit]`` metadata at all -- a directory the builder did not
    create, where the app package has to be guessed rather than read.
    """
    from quadkit.cli.layout import read_project_layout, resolve_output_dir

    layout = read_project_layout()
    if not layout.declared:
        return _detect_src_dir(default)
    try:
        return resolve_output_dir(
            default,
            app_package=layout.app_package,
            module=module,
            generator=generator,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


def _detect_src_dir(default: str) -> str:
    """Rewrite package-local ``src`` defaults for single-package layouts."""
    default_path = Path(default)
    if not default_path.parts or default_path.parts[0] != "src":
        return default

    src_dir = Path.cwd() / "src"
    if not src_dir.is_dir():
        return default

    packages = [
        package_dir
        for package_dir in src_dir.iterdir()
        if package_dir.is_dir() and (package_dir / "__init__.py").is_file()
    ]
    if len(packages) != 1:
        return default

    package_relative_parts = ["src", packages[0].name, *default_path.parts[1:]]
    return str(Path(*package_relative_parts))


class CommandAssembler:
    """Wires generator definitions from all CLI contributors onto a Typer app."""

    def __init__(
        self,
        contributor_registry: CliContributorRegistry,
        generator_registry: GeneratorRegistry,
    ) -> None:
        self._contributor_registry = contributor_registry
        self._generator_registry = generator_registry

    def assemble(self, app: typer.Typer) -> None:
        """Register a Typer subcommand for every generator from all contributors."""
        for contributor in self._contributor_registry.get_all():
            for generator_definition in contributor.get_generators():
                self._register_command(app, generator_definition)

    def _register_command(
        self,
        app: typer.Typer,
        gen_def: GeneratorDefinition,
    ) -> None:
        """Register a single executable Typer subcommand for *gen_def*."""
        generator_name = gen_def.name
        registry = self._generator_registry

        @handle_errors
        def _command(
            name: str,
            fields: Annotated[
                str | None,
                typer.Option("--fields", "-f", help="Fields in name:type format"),
            ] = None,
            output_dir: Annotated[
                str,
                typer.Option("--output-dir", "-o", help="Output directory"),
            ] = gen_def.default_output_dir,
            module: Annotated[
                str | None,
                typer.Option(
                    "--module",
                    "-m",
                    help="Bounded context this belongs to (omit for app-level code)",
                ),
            ] = None,
            dry_run: Annotated[
                bool,
                typer.Option(
                    "--dry-run",
                    help="Show what would be generated without writing to disk",
                ),
            ] = False,
            force: Annotated[
                bool,
                typer.Option("--force", help="Overwrite existing files"),
            ] = False,
        ) -> None:
            definition = registry.get(generator_name)
            if definition is None:
                typer.echo(
                    f"Generator {generator_name} is not registered "
                    "in the generator registry.",
                    err=True,
                )
                raise typer.Exit(1)

            adapter = registry.get_adapter(generator_name)
            if adapter is None:
                typer.echo(
                    f"Generator {generator_name} is not registered "
                    "in the generator registry.",
                    err=True,
                )
                raise typer.Exit(1)

            kwargs: dict[str, object] = {"dry_run": dry_run, "force": force}
            if fields:
                kwargs["fields_str"] = fields

            resolved_output = output_dir
            if output_dir == definition.default_output_dir:
                resolved_output = _resolve_default_output(
                    output_dir, generator_name, module
                )

            result = adapter.generate(name, output_dir=resolved_output, **kwargs)
            output = OutputManager()
            if result.success:
                created = result.files_created or []
                updated = result.files_updated or []
                for file_path in created:
                    output.success(f"Created: {file_path}")
                for file_path in updated:
                    output.warning(f"Overwrote: {file_path}")
                if not created and not updated:
                    output.info("No files generated")
                return

            output.error(f"Generation failed: {result.error}")
            raise typer.Exit(1)

        _command.__name__ = generator_name.replace("-", "_")
        app.command(generator_name, help=_build_help_text(gen_def))(_command)


def _build_help_text(gen_def: GeneratorDefinition) -> str:
    """Compose command help: description plus any declared generator options."""
    if not gen_def.options:
        return gen_def.description
    lines = [f"{gen_def.description}", "", "Options:"]
    for option in gen_def.options:
        default_note = f" [default: {option.default}]" if option.default else ""
        option_line = (
            f"  --{option.name} ({option.type_hint}){default_note} {option.description}"
        )
        lines.append(option_line.rstrip())
    return "\n".join(lines)


__all__ = ["CommandAssembler"]
