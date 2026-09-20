"""Code generation commands assembled from discovered CLI contributors."""

from __future__ import annotations

import typer

from quadkit.cli.assembly.assembler import CommandAssembler
from quadkit.cli.contributors.discovery import populate_cli_registries
from quadkit.cli.contributors.registry import CliContributorRegistry
from quadkit.cli.output import OutputManager
from quadkit.cli.registry.generator import GeneratorRegistry

app = typer.Typer()

_assembled = False
_RUNTIME_GENERATOR_REGISTRY: GeneratorRegistry | None = None


def _build_runtime_registries() -> tuple[CliContributorRegistry, GeneratorRegistry]:
    """Build contributor and generator registries from runtime discovery."""
    contributor_registry = CliContributorRegistry()
    generator_registry = GeneratorRegistry()
    populate_cli_registries(contributor_registry, generator_registry)
    return contributor_registry, generator_registry


def _assemble_runtime_commands(target_app: typer.Typer) -> GeneratorRegistry:
    """Populate *target_app* from discovered contributors and return the registry."""
    contributor_registry, generator_registry = _build_runtime_registries()
    CommandAssembler(contributor_registry, generator_registry).assemble(target_app)
    return generator_registry


def assemble_gen_commands(target_app: typer.Typer, assembler: object) -> None:
    """Populate *target_app* using a ``CommandAssembler`` resolved from DI."""
    if not isinstance(assembler, CommandAssembler):
        raise TypeError(
            f"assembler must be a CommandAssembler instance, got {type(assembler)!r}"
        )
    assembler.assemble(target_app)


def _ensure_assembled(target_app: typer.Typer) -> None:
    """Populate *target_app* from discovered contributors on first invocation."""
    global _assembled, _RUNTIME_GENERATOR_REGISTRY
    if not _assembled:
        _RUNTIME_GENERATOR_REGISTRY = _assemble_runtime_commands(target_app)
        _assembled = True


@app.callback(invoke_without_command=True)
def gen_callback(ctx: typer.Context) -> None:
    """Code generation commands assembled from discovered CLI contributors."""
    _ensure_assembled(app)
    if ctx.invoked_subcommand is None:
        if (
            not _RUNTIME_GENERATOR_REGISTRY
            or not _RUNTIME_GENERATOR_REGISTRY.list_generators()
        ):
            OutputManager().info("No generators discovered")
        else:
            typer.echo(ctx.get_help())


@app.command("list")
def list_generators() -> None:
    """List all available generators."""
    _ensure_assembled(app)
    output = OutputManager()
    assert _RUNTIME_GENERATOR_REGISTRY is not None  # noqa: S101  # set by _ensure_assembled
    generators = _RUNTIME_GENERATOR_REGISTRY.list_generators()
    if not generators:
        output.info("No generators discovered")
        return

    output.print("[bold]Available generators:[/bold]")
    for generator in generators:
        output.print(f"  [cyan]{generator.name}[/cyan] - {generator.description}")


# Assemble runtime commands immediately on import so subcommands are available
# for routing. The guard inside _ensure_assembled prevents double-assembly on
# subsequent calls (e.g. from the callback or after a module reload).
_ensure_assembled(app)

__all__ = ["app", "assemble_gen_commands"]
