from __future__ import annotations

import pytest
import typer

from quadkit.cli.assembly import CommandAssembler
from quadkit.cli.contributors.base import BaseCliContributor
from quadkit.cli.contributors.core import _GENERATOR_SPECS, CoreCliContributor
from quadkit.cli.contributors.registry import CliContributorRegistry
from quadkit.cli.registry.generator import GeneratorRegistry
from quadkit.contracts.cli.protocols import CliContributorProtocol
from quadkit.contracts.cli.types import GeneratorDefinition

from ._test_cli_contribution_system_support import (
    _FakeContributor,
)


class TestCliContracts:
    def test_generator_definition_is_frozen(self) -> None:
        gen = GeneratorDefinition(
            name="model",
            title="Generate Model",
            description="Scaffolds a domain model",
            contributor="core",
            generator_path="tests.fake:FakeGenerator",
        )
        with pytest.raises(AttributeError):
            gen.name = "other"  # type: ignore[misc]

    def test_generator_definition_defaults(self) -> None:
        gen = GeneratorDefinition(
            name="model",
            title="Generate Model",
            description="Scaffolds a domain model",
            contributor="core",
            generator_path="tests.fake:FakeGenerator",
        )
        assert gen.category == "general"
        assert gen.options == ()

    def test_cli_contributor_protocol_is_runtime_checkable(self) -> None:
        # isinstance() would raise TypeError if @runtime_checkable were missing
        assert isinstance(object(), CliContributorProtocol) is False

    def test_generator_definition_requires_generator_path(self) -> None:
        with pytest.raises(TypeError):
            GeneratorDefinition(
                name="model",
                title="Generate Model",
                description="Scaffolds a domain model",
                contributor="core",
            )


class TestGeneratorRegistryInstanceBased:
    def test_new_registry_is_empty(self) -> None:
        registry = GeneratorRegistry()
        assert registry.list_generators() == []

    def test_register_adds_generator(self) -> None:
        registry = GeneratorRegistry()
        gen = GeneratorDefinition(
            name="model",
            title="Generate Model",
            description="Scaffolds a domain model",
            contributor="core",
            generator_path="tests.fake:FakeGenerator",
        )
        registry.register(gen)
        assert len(registry.list_generators()) == 1
        assert registry.get("model") is gen

    def test_registry_instances_are_independent(self) -> None:
        r1 = GeneratorRegistry()
        r2 = GeneratorRegistry()
        gen = GeneratorDefinition(
            name="x",
            title="X",
            description="X",
            contributor="c",
            generator_path="tests.fake:FakeGenerator",
        )
        r1.register(gen)
        assert r2.list_generators() == []  # r2 must not see r1's generators


from quadkit.cli.contributors.base import BaseCliContributor
from quadkit.cli.contributors.registry import CliContributorRegistry


class TestBaseCliContributor:
    def test_base_contributor_has_contributor_id(self) -> None:
        class MyContributor(BaseCliContributor):
            @property
            def contributor_id(self) -> str:
                return "my_contrib"

        contrib = MyContributor()
        assert contrib.contributor_id == "my_contrib"

    def test_base_contributor_get_generators_returns_empty(self) -> None:
        class MyContributor(BaseCliContributor):
            @property
            def contributor_id(self) -> str:
                return "my_contrib"

        contrib = MyContributor()
        assert contrib.get_generators() == []


class TestCliContributorRegistry:
    def test_new_registry_is_empty(self) -> None:
        registry = CliContributorRegistry()
        assert registry.get_all() == []

    def test_register_contributor(self) -> None:
        class MyContributor(BaseCliContributor):
            @property
            def contributor_id(self) -> str:
                return "test"

            def get_generators(self):
                return []

        registry = CliContributorRegistry()
        contrib = MyContributor()
        registry.register(contrib)
        assert len(registry.get_all()) == 1

    def test_registry_instances_are_independent(self) -> None:
        class MyContributor(BaseCliContributor):
            @property
            def contributor_id(self) -> str:
                return "test"

        r1 = CliContributorRegistry()
        r2 = CliContributorRegistry()
        r1.register(MyContributor())
        assert r2.get_all() == []


from quadkit.cli.contributors.core import _GENERATOR_SPECS, CoreCliContributor

# The set of generator names expected from _GENERATOR_SPECS.
_EXPECTED_CORE_NAMES: frozenset[str] = frozenset(
    name for name, *_ in _GENERATOR_SPECS
)


class TestCoreCliContributor:
    def test_core_contributor_id_is_core(self) -> None:
        """contributor_id must return the string 'core'."""
        contrib = CoreCliContributor()
        assert contrib.contributor_id == "core"

    def test_core_contributor_get_generators_returns_list_of_generator_definitions(
        self,
    ) -> None:
        """get_generators() must return a list of GeneratorDefinition instances."""
        from quadkit.contracts.cli.types import GeneratorDefinition

        contrib = CoreCliContributor()
        generators = contrib.get_generators()
        assert isinstance(generators, list)
        assert len(generators) > 0
        for item in generators:
            assert isinstance(item, GeneratorDefinition)

    def test_core_contributor_generator_names_match_expected(self) -> None:
        """Generator names must exactly match the _CORE_ADAPTERS mapping."""
        contrib = CoreCliContributor()
        actual_names = {g.name for g in contrib.get_generators()}
        assert actual_names == _EXPECTED_CORE_NAMES

    def test_core_contributor_does_not_expose_moved_web_or_sql_generators(self) -> None:
        contrib = CoreCliContributor()
        actual_names = {g.name for g in contrib.get_generators()}

        assert actual_names.isdisjoint(
            {
                "controller",
                "resource",
                "middleware",
                "graphql",
                "webhook",
                "websocket",
                "repository",
                "filter",
                "seeder",
                "health",
            }
        )

    def test_core_contributor_does_not_include_moved_generators(self) -> None:
        contrib = CoreCliContributor()
        names = {g.name for g in contrib.get_generators()}

        assert "model" not in names
        assert "service" not in names
        assert "event" not in names
        assert "command" not in names
        assert "query" not in names
        assert "guard" not in names

    def test_core_contributor_get_generators_returns_fresh_list(self) -> None:
        """Each call to get_generators() returns an independent list."""
        contrib = CoreCliContributor()
        first = contrib.get_generators()
        second = contrib.get_generators()
        assert first == second
        assert first is not second

    def test_populate_registers_core_generators(self) -> None:
        """populate_cli_registries() must register core generators via discovery."""
        from quadkit.cli.contributors.discovery import populate_cli_registries

        contributor_registry = CliContributorRegistry()
        generator_registry = GeneratorRegistry()
        populate_cli_registries(
            contributor_registry,
            generator_registry,
            contributors=[CoreCliContributor()],
        )
        registered_names = {g.name for g in generator_registry.list_generators()}
        assert registered_names == _EXPECTED_CORE_NAMES

    def test_populate_does_not_affect_unrelated_registry(self) -> None:
        """A fresh GeneratorRegistry() stays empty until populated."""
        from quadkit.cli.contributors.discovery import populate_cli_registries

        bare = GeneratorRegistry()
        contributor_registry = CliContributorRegistry()
        generator_registry = GeneratorRegistry()
        populate_cli_registries(
            contributor_registry,
            generator_registry,
            contributors=[CoreCliContributor()],
        )
        assert bare.list_generators() == []


import typer

from quadkit.cli.assembly import CommandAssembler


class TestCommandAssembler:
    def test_assemble_registers_commands_for_all_generators(self) -> None:
        """assemble() must register one Typer command per generator across all contributors."""
        contributor_registry = CliContributorRegistry()
        contributor_registry.register(_FakeContributor("plugin-a", ["alpha", "beta"]))
        contributor_registry.register(_FakeContributor("plugin-b", ["gamma"]))

        generator_registry = GeneratorRegistry()

        assembler = CommandAssembler(contributor_registry, generator_registry)
        app = typer.Typer()
        assembler.assemble(app)

        registered_names = {cmd.name for cmd in app.registered_commands}
        assert "alpha" in registered_names
        assert "beta" in registered_names
        assert "gamma" in registered_names
        assert len(app.registered_commands) == 3

    def test_assemble_with_empty_registry_registers_no_commands(self) -> None:
        """assemble() against an empty contributor registry must add no commands."""
        contributor_registry = CliContributorRegistry()
        generator_registry = GeneratorRegistry()

        assembler = CommandAssembler(contributor_registry, generator_registry)
        app = typer.Typer()
        assembler.assemble(app)

        assert app.registered_commands == []

    def test_definition_command_executes_registry_loaded_adapter(
        self, tmp_path, monkeypatch
    ) -> None:
        """Assembler commands must execute using the generator definition metadata."""
        from pathlib import Path
        import sys
        from types import ModuleType

        from typer.testing import CliRunner

        from quadkit.cli.generators.base import GenerationResult

        module_name = "fake_cli_generator_module"
        module = ModuleType(module_name)

        class FakeGenerator:
            def __init__(self, output_dir: str = "src") -> None:
                self.output_dir = output_dir

            def generate(self, name: str, **_: object) -> GenerationResult:
                result = GenerationResult()
                result.files_created.append(Path(self.output_dir) / f"{name}.py")
                return result

        module.FakeGenerator = FakeGenerator
        sys.modules[module_name] = module

        gen_def = GeneratorDefinition(
            name="widget",
            title="Widget",
            description="Generate widget",
            contributor="plugin",
            generator_path=f"{module_name}:FakeGenerator",
            default_output_dir="src/widgets",
        )

        class _GeneratorContributor:
            @property
            def contributor_id(self) -> str:
                return "plugin"

            def get_generators(self) -> list[GeneratorDefinition]:
                return [gen_def]

        contributor_registry = CliContributorRegistry()
        contributor_registry.register(_GeneratorContributor())

        generator_registry = GeneratorRegistry()
        generator_registry.register(gen_def)

        assembler = CommandAssembler(contributor_registry, generator_registry)
        app = typer.Typer()
        assembler.assemble(app)

        runner = CliRunner()
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["Gizmo"])

        assert result.exit_code == 0, result.output
        assert "Created: src/widgets/Gizmo.py" in result.output

        del sys.modules[module_name]



