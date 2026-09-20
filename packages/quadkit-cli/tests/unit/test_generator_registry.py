"""Tests for GeneratorRegistry and GeneratorAdapter dispatch.

Verifies the instance-based GeneratorRegistry API and that every core
generator adapter can produce a successful result without raising.
"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
import tempfile

import pytest

from quadkit.cli.registry.generator import GeneratorAdapter, GeneratorRegistry
from quadkit.contracts.cli.types import GeneratorDefinition

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def output_dir() -> Generator[Path, None, None]:
    """Temporary directory for generator output files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def _build_adapter_map() -> dict[str, GeneratorAdapter]:
    """Build the full adapter map directly from generator classes.

    This replicates the trimmed core contributor wiring so that integration
    tests can run without a populated GeneratorRegistry.
    """
    from quadkit.cli.generators.provider import ProviderGenerator
    from quadkit.cli.generators.test import TestGenerator

    pairs: list[tuple[type, str]] = [
        (ProviderGenerator, "src/providers"),
        (TestGenerator, "tests/unit"),
    ]
    result: dict[str, GeneratorAdapter] = {}
    for cls, output in pairs:
        adapter = GeneratorAdapter(cls, output)
        result[adapter.get_name()] = adapter
    return result


_ALL_REGISTERED_NAMES = [
    "provider",
    "test",
]


# ---------------------------------------------------------------------------
# Instance-based registry — API contract
# ---------------------------------------------------------------------------


class TestGeneratorRegistryAPI:
    """Verify the instance-based GeneratorRegistry API contract."""

    def test_new_registry_is_empty(self) -> None:
        assert GeneratorRegistry().list_generators() == []

    def test_register_and_get_roundtrip(self) -> None:
        registry = GeneratorRegistry()
        gen = GeneratorDefinition(
            name="model",
            title="Generate Model",
            description="Scaffolds a domain model",
            contributor="core",
            generator_path="tests.fake:FakeGenerator",
        )
        registry.register(gen)
        assert registry.get("model") is gen

    def test_get_unknown_returns_none(self) -> None:
        assert GeneratorRegistry().get("nonexistent_xyz") is None

    def test_list_generators_returns_insertion_order(self) -> None:
        registry = GeneratorRegistry()
        a = GeneratorDefinition(
            name="a",
            title="A",
            description="A",
            contributor="c",
            generator_path="tests.fake:FakeGenerator",
        )
        b = GeneratorDefinition(
            name="b",
            title="B",
            description="B",
            contributor="c",
            generator_path="tests.fake:FakeGenerator",
        )
        registry.register(a)
        registry.register(b)
        names = [g.name for g in registry.list_generators()]
        assert names == ["a", "b"]

    def test_register_overwrites_duplicate_name(self) -> None:
        registry = GeneratorRegistry()
        first = GeneratorDefinition(
            name="x",
            title="First",
            description="First",
            contributor="c",
            generator_path="tests.fake:FakeGenerator",
        )
        second = GeneratorDefinition(
            name="x",
            title="Second",
            description="Second",
            contributor="c",
            generator_path="tests.fake:FakeGenerator",
        )
        registry.register(first)
        registry.register(second)
        assert len(registry.list_generators()) == 1
        assert registry.get("x") is second

    def test_instances_are_independent(self) -> None:
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
        assert r2.list_generators() == []


# ---------------------------------------------------------------------------
# Adapter dispatch — name / description contract
# ---------------------------------------------------------------------------


class TestGeneratorAdapterDispatch:
    """Verify adapters expose the correct names and descriptions."""

    def setup_method(self) -> None:
        self._adapters = _build_adapter_map()

    def test_all_expected_adapters_are_present(self) -> None:
        for name in _ALL_REGISTERED_NAMES:
            assert name in self._adapters, f"Adapter '{name}' not found"

    @pytest.mark.parametrize("name", _ALL_REGISTERED_NAMES)
    def test_adapter_get_name_matches_key(self, name: str) -> None:
        adapter = _build_adapter_map()[name]
        assert adapter.get_name() == name

    @pytest.mark.parametrize("name", _ALL_REGISTERED_NAMES)
    def test_adapter_get_description_is_non_empty(self, name: str) -> None:
        adapter = _build_adapter_map()[name]
        description = adapter.get_description()
        assert isinstance(description, str)
        assert description.strip() != ""


# ---------------------------------------------------------------------------
# Generation dispatch — each generator produces a successful result
# ---------------------------------------------------------------------------


class TestGeneratorDispatchGenerate:
    """Verify that every core generator adapter can generate without raising."""

    @pytest.mark.parametrize("name", _ALL_REGISTERED_NAMES)
    def test_generate_returns_success(self, name: str, output_dir: Path) -> None:
        """GeneratorAdapter.generate() must succeed for every core generator."""
        adapter = _build_adapter_map()[name]
        adapter._default_output = str(output_dir)
        result = adapter.generate("Widget", output_dir=str(output_dir), dry_run=True)
        assert result.success, f"Generator '{name}' failed: {result.error!r}"

    @pytest.mark.parametrize("name", _ALL_REGISTERED_NAMES)
    def test_generate_with_dry_run_creates_no_files(
        self, name: str, output_dir: Path
    ) -> None:
        """dry_run=True must not write any files to disk."""
        adapter = _build_adapter_map()[name]
        adapter._default_output = str(output_dir)
        adapter.generate("Widget", output_dir=str(output_dir), dry_run=True)
        created = list(output_dir.rglob("*.py"))
        assert created == [], (
            f"Generator '{name}' wrote files during dry_run: {created}"
        )
