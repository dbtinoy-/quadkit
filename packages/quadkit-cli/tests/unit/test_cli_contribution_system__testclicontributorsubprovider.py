from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import typer
from typer.testing import CliRunner

from quadkit.cli.assembly import CommandAssembler
from quadkit.cli.commands.contrib import app as plugin_app
from quadkit.cli.contributors.core import CoreCliContributor
from quadkit.cli.contributors.registry import CliContributorRegistry
from quadkit.cli.di.sub_providers.contributor import CliContributorSubProvider
from quadkit.cli.registry.generator import GeneratorRegistry
from quadkit.contracts.cli.types import GeneratorDefinition


class TestCliProviderWiring:
    def test_core_contributor_entry_point_declared(self) -> None:
        """The quadkit.cli.contributors entry-point group must be declared in pyproject.toml."""
        import pathlib
        import tomllib  # stdlib in 3.11+

        pyproject_path = pathlib.Path(__file__).parent.parent.parent / "pyproject.toml"
        data = tomllib.loads(pyproject_path.read_text())

        entry_points = data.get("project", {}).get("entry-points", {})
        group = entry_points.get("quadkit.cli.contributors", {})

        assert "core" in group, (
            "Expected 'core' key in [project.entry-points.\"quadkit.cli.contributors\"]"
        )
        assert group["core"] == "quadkit.cli.contributors.core:CoreCliContributor", (
            f"Expected entry point to point to CoreCliContributor, got: {group['core']!r}"
        )

    def test_cli_provider_composes_contributor_sub_provider(self) -> None:
        """CLIProvider must compose a CliContributorSubProvider instance."""
        from quadkit.cli.di.provider import CLIProvider

        provider = CLIProvider()
        assert hasattr(provider, "_contributor_sub_provider"), (
            "CLIProvider must hold a _contributor_sub_provider attribute"
        )
        assert isinstance(provider._contributor_sub_provider, CliContributorSubProvider)

    @pytest.mark.asyncio
    async def test_cli_provider_register_delegates_to_sub_provider(self) -> None:
        """CLIProvider.register() must delegate to CliContributorSubProvider.register()."""
        from unittest.mock import AsyncMock, patch

        from quadkit.cli.di.provider import CLIProvider
        from quadkit.cli.di.sub_providers.contributor import CliContributorSubProvider

        provider = CLIProvider()
        container = MagicMock()

        with patch.object(
            CliContributorSubProvider,
            "register",
            new_callable=AsyncMock,
        ) as mock_register:
            await provider.register(container)

        mock_register.assert_awaited_once_with(container)

    @pytest.mark.asyncio
    async def test_cli_provider_boot_delegates_to_sub_provider(self) -> None:
        """CLIProvider.boot() must delegate to CliContributorSubProvider.boot()."""
        from unittest.mock import AsyncMock, patch

        from quadkit.cli.di.provider import CLIProvider
        from quadkit.cli.di.sub_providers.contributor import CliContributorSubProvider

        provider = CLIProvider()
        container = MagicMock()

        with patch.object(
            CliContributorSubProvider,
            "boot",
            new_callable=AsyncMock,
        ) as mock_boot:
            await provider.boot(container)

        mock_boot.assert_awaited_once_with(container)


class TestCliContributorSubProvider:
    @pytest.mark.asyncio
    async def test_register_binds_registries(self) -> None:
        """register() must call singleton for contribution-system runtime types."""
        sub_provider = CliContributorSubProvider()
        container = MagicMock()

        await sub_provider.register(container)

        registered_types = {c.args[0] for c in container.singleton.call_args_list}
        assert CliContributorRegistry in registered_types
        assert GeneratorRegistry in registered_types
        assert CommandAssembler in registered_types
        assert CoreCliContributor not in registered_types

    @pytest.mark.asyncio
    async def test_boot_entry_point_registers_contributors_in_both_registries(
        self,
    ) -> None:
        """boot() must populate both registries from runtime discovery."""
        from unittest.mock import patch

        sub_provider = CliContributorSubProvider()
        contributor_registry = CliContributorRegistry()
        generator_registry = GeneratorRegistry()

        async def _resolve(service_type: type) -> object:
            if service_type is CliContributorRegistry:
                return contributor_registry
            if service_type is GeneratorRegistry:
                return generator_registry
            raise ValueError(f"Unexpected resolve for {service_type}")

        container = MagicMock()
        container.resolve = AsyncMock(side_effect=_resolve)

        with patch(
            "quadkit.cli.di.sub_providers.contributor.populate_cli_registries"
        ) as mock_populate:
            await sub_provider.boot(container)

        mock_populate.assert_called_once_with(contributor_registry, generator_registry)


# ---------------------------------------------------------------------------
# T13: plugin list command
# ---------------------------------------------------------------------------

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from quadkit.cli.commands.contrib import app as plugin_app


class TestPluginListCommand:
    """Tests for the ``quadkit plugin list`` entry-point discovery command."""

    def test_plugin_list_discovers_core_contributor(self) -> None:
        """plugin list must display contributor id and generator count for a discovered EP.

        Mocks ``importlib.metadata.entry_points`` inside the plugin command
        module to return a single fake entry point that loads
        ``CoreCliContributor``; asserts the output contains the contributor
        name ``"core"`` and the expected generator count.
        """
        from quadkit.cli.contributors.core import CoreCliContributor

        fake_ep = MagicMock()
        fake_ep.name = "core"
        fake_ep.load.return_value = CoreCliContributor

        runner = CliRunner()
        with patch(
            "quadkit.cli.contributors.runtime.entry_points",
            return_value=[fake_ep],
        ):
            result = runner.invoke(plugin_app, ["list"])

        assert result.exit_code == 0, result.output
        assert "core" in result.output
        assert "2" in result.output

    def test_plugin_list_shows_generator_names_preview(self) -> None:
        """plugin list must include at least the first generator name in the output."""
        from quadkit.cli.contributors.core import CoreCliContributor

        fake_ep = MagicMock()
        fake_ep.name = "core"
        fake_ep.load.return_value = CoreCliContributor

        runner = CliRunner()
        with patch(
            "quadkit.cli.contributors.runtime.entry_points",
            return_value=[fake_ep],
        ):
            result = runner.invoke(plugin_app, ["list"])

        assert result.exit_code == 0, result.output
        assert "provider" in result.output

    def test_plugin_list_with_no_contributors(self) -> None:
        """plugin list must gracefully report when no entry points are found."""
        runner = CliRunner()
        with patch(
            "quadkit.cli.contributors.runtime.entry_points",
            return_value=[],
        ):
            result = runner.invoke(plugin_app, ["list"])

        assert result.exit_code == 0, result.output
        assert "no" in result.output.lower() or "found" in result.output.lower()

    def test_plugin_list_handles_load_failure_gracefully(self) -> None:
        """plugin list must continue and report an error for a contributor that fails to load."""
        fake_ep = MagicMock()
        fake_ep.name = "broken"
        fake_ep.load.side_effect = ImportError("missing dependency")

        runner = CliRunner()
        with patch(
            "quadkit.cli.contributors.runtime.entry_points",
            return_value=[fake_ep],
        ):
            result = runner.invoke(plugin_app, ["list"])

        assert result.exit_code == 0, result.output
        assert "broken" in result.output
        assert "failed" in result.output.lower() or "missing" in result.output.lower()

    def test_plugin_list_multiple_contributors(self) -> None:
        """plugin list must list every contributor when multiple entry points are present."""
        from quadkit.contracts.cli.types import GeneratorDefinition

        class _AlphaContributor:
            @property
            def contributor_id(self) -> str:
                return "alpha"

            def get_generators(self) -> list[GeneratorDefinition]:
                return [
                    GeneratorDefinition(
                        name="thing",
                        title="Thing",
                        description="A thing",
                        contributor="alpha",
                        generator_path="tests.fake:FakeGenerator",
                    )
                ]

        class _BetaContributor:
            @property
            def contributor_id(self) -> str:
                return "beta"

            def get_generators(self) -> list[GeneratorDefinition]:
                return []

        ep_alpha = MagicMock()
        ep_alpha.name = "alpha"
        ep_alpha.load.return_value = _AlphaContributor

        ep_beta = MagicMock()
        ep_beta.name = "beta"
        ep_beta.load.return_value = _BetaContributor

        runner = CliRunner()
        with patch(
            "quadkit.cli.contributors.runtime.entry_points",
            return_value=[ep_alpha, ep_beta],
        ):
            result = runner.invoke(plugin_app, ["list"])

        assert result.exit_code == 0, result.output
        assert "alpha" in result.output
        assert "beta" in result.output


class TestCommandAssemblerPackageLayout:
    def test_definition_command_preserves_src_suffix_for_package_layout(
        self, tmp_path, monkeypatch
    ) -> None:
        from pathlib import Path
        import sys
        from types import ModuleType

        from typer.testing import CliRunner

        from quadkit.cli.generators.base import GenerationResult

        module_name = "fake_cli_package_layout_module"
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
            name="model",
            title="Model",
            description="Generate model",
            contributor="plugin",
            generator_path=f"{module_name}:FakeGenerator",
            default_output_dir="src/models",
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
        try:
            package_dir = Path("src") / "petclinic"
            package_dir.mkdir(parents=True)
            (package_dir / "__init__.py").write_text("")
            result = runner.invoke(app, ["Gizmo"])
        finally:
            sys.modules.pop(module_name, None)

        assert result.exit_code == 0, result.output
        assert "Created: src/petclinic/models/Gizmo.py" in result.output


class TestCliContributorDiscovery:
    def test_load_cli_contributors_skips_bad_entry_point_load(self, capsys) -> None:
        from unittest.mock import MagicMock, patch

        from quadkit.cli.contributors.discovery import load_cli_contributors

        class _HealthyContributor:
            @property
            def contributor_id(self) -> str:
                return "healthy"

            def get_generators(self) -> list[GeneratorDefinition]:
                return []

        broken_entry_point = MagicMock()
        broken_entry_point.name = "broken-load"
        broken_entry_point.load.side_effect = ImportError("missing dependency")

        healthy_entry_point = MagicMock()
        healthy_entry_point.name = "healthy"
        healthy_entry_point.load.return_value = _HealthyContributor

        with patch(
            "quadkit.cli.contributors.runtime.entry_points",
            return_value=[broken_entry_point, healthy_entry_point],
        ):
            contributors = load_cli_contributors()

        assert [contributor.contributor_id for contributor in contributors] == [
            "healthy"
        ]
        captured = capsys.readouterr()
        assert "broken-load" in captured.out
        assert "missing dependency" in captured.out

    def test_load_cli_contributors_skips_bad_constructor(self, capsys) -> None:
        from unittest.mock import MagicMock, patch

        from quadkit.cli.contributors.discovery import load_cli_contributors

        class _BrokenContributor:
            def __init__(self) -> None:
                raise RuntimeError("constructor exploded")

        class _HealthyContributor:
            @property
            def contributor_id(self) -> str:
                return "healthy"

            def get_generators(self) -> list[GeneratorDefinition]:
                return []

        broken_entry_point = MagicMock()
        broken_entry_point.name = "broken-constructor"
        broken_entry_point.load.return_value = _BrokenContributor

        healthy_entry_point = MagicMock()
        healthy_entry_point.name = "healthy"
        healthy_entry_point.load.return_value = _HealthyContributor

        with patch(
            "quadkit.cli.contributors.runtime.entry_points",
            return_value=[broken_entry_point, healthy_entry_point],
        ):
            contributors = load_cli_contributors()

        assert [contributor.contributor_id for contributor in contributors] == [
            "healthy"
        ]
        captured = capsys.readouterr()
        assert "broken-constructor" in captured.out
        assert "constructor exploded" in captured.out

    def test_gen_module_reload_tolerates_broken_contributor(self, capsys) -> None:
        import importlib
        from unittest.mock import MagicMock, patch

        from typer.testing import CliRunner

        from quadkit.cli.commands import gen as gen_module

        broken_entry_point = MagicMock()
        broken_entry_point.name = "broken-load"
        broken_entry_point.load.side_effect = ImportError("missing dependency")

        try:
            with patch(
                "quadkit.cli.contributors.runtime.entry_points",
                return_value=[broken_entry_point],
            ):
                reloaded_module = importlib.reload(gen_module)

            runner = CliRunner()
            result = runner.invoke(reloaded_module.app, [])

            assert result.exit_code == 0, result.output
            assert "No generators discovered" in result.output
            captured = capsys.readouterr()
            assert "broken-load" in captured.out
            assert "missing dependency" in captured.out
        finally:
            importlib.reload(gen_module)


# ---------------------------------------------------------------------------
# T14: CacheCliContributor runtime discovery via populate_cli_registries
# ---------------------------------------------------------------------------


class TestCacheCliContributorDiscovery:
    """Verify populate_cli_registries wires CacheCliContributor into both registries."""

    @pytest.mark.asyncio
    async def test_populate_registers_cache_repo_generator(self) -> None:
        """populate_cli_registries with CacheCliContributor must register cache_repo."""
        from quadkit.cache.cli.contributor import CacheCliContributor
        from quadkit.cli.contributors.discovery import populate_cli_registries
        from quadkit.cli.contributors.registry import CliContributorRegistry
        from quadkit.cli.registry.generator import GeneratorRegistry

        contributor_registry = CliContributorRegistry()
        generator_registry = GeneratorRegistry()

        populate_cli_registries(
            contributor_registry,
            generator_registry,
            contributors=[CacheCliContributor()],
        )

        assert contributor_registry.get("cache") is not None
        assert generator_registry.get("cache_repo") is not None

    def test_cache_contributor_generator_path_points_to_package_local(self) -> None:
        """CacheCliContributor's generator_path must point to quadkit.cache, not quadkit.cli."""
        from quadkit.cache.cli.contributor import CacheCliContributor

        contributor = CacheCliContributor()
        definitions = {g.name: g for g in contributor.get_generators()}

        assert "cache_repo" in definitions
        path = definitions["cache_repo"].generator_path
        assert path.startswith("quadkit.cache."), (
            f"generator_path must be in quadkit.cache package, got: {path}"
        )
        assert "quadkit.cli" not in path
