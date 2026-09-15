"""Tests for CLI contributor registry."""

from __future__ import annotations

from quadkit.cli.contributors.registry import CliContributorRegistry
from quadkit.contracts.cli.protocols import CliContributorProtocol
from quadkit.contracts.cli.types import GeneratorDefinition


class MockContributor:
    """Mock contributor implementing CliContributorProtocol."""

    def __init__(self, contributor_id: str, generator_count: int = 0) -> None:
        self._contributor_id = contributor_id
        self._generator_count = generator_count

    @property
    def contributor_id(self) -> str:
        return self._contributor_id

    def get_generators(self) -> list[GeneratorDefinition]:
        return [
            GeneratorDefinition(
                name=f"generator-{i}",
                title=f"Generate Generator {i}",
                description=f"Description for generator {i}",
                contributor=self._contributor_id,
                generator_path="tests.fake:FakeGenerator",
            )
            for i in range(self._generator_count)
        ]

    def get_commands(self) -> list:
        return []

    def get_health_checks(self) -> list:
        return []

    def get_doctor_checks(self) -> list:
        return []

    def get_shell_context(self) -> list:
        return []

    def get_hooks(self) -> list:
        return []


class TestCliContributorRegistry:
    """Tests for CliContributorRegistry."""

    def test_register_single_contributor(self) -> None:
        """Test registering a single contributor."""
        registry = CliContributorRegistry()
        contributor = MockContributor("core", generator_count=0)

        registry.register(contributor)

        result = registry.get("core")
        assert result is not None
        assert result.contributor_id == "core"

    def test_register_multiple_contributors(self) -> None:
        """Test registering multiple contributors."""
        registry = CliContributorRegistry()
        core = MockContributor("core", generator_count=0)
        web = MockContributor("web", generator_count=0)
        sql = MockContributor("sql", generator_count=0)

        registry.register(core)
        registry.register(web)
        registry.register(sql)

        assert registry.get("core") is not None
        assert registry.get("web") is not None
        assert registry.get("sql") is not None

    def test_register_duplicate_overwrites(self) -> None:
        """Test that registering same ID overwrites previous contributor."""
        registry = CliContributorRegistry()
        contributor1 = MockContributor("core", generator_count=1)
        contributor2 = MockContributor("core", generator_count=2)

        registry.register(contributor1)
        assert registry.get("core") is not None

        registry.register(contributor2)
        result = registry.get("core")
        assert result is not None

    def test_get_nonexistent_returns_none(self) -> None:
        """Test that getting nonexistent contributor returns None."""
        registry = CliContributorRegistry()

        result = registry.get("nonexistent")
        assert result is None

    def test_get_all_empty_registry(self) -> None:
        """Test get_all returns empty list for empty registry."""
        registry = CliContributorRegistry()

        result = registry.get_all()
        assert result == []

    def test_get_all_returns_all_contributors(self) -> None:
        """Test get_all returns all registered contributors."""
        registry = CliContributorRegistry()
        core = MockContributor("core", generator_count=0)
        web = MockContributor("web", generator_count=0)
        sql = MockContributor("sql", generator_count=0)

        registry.register(core)
        registry.register(web)
        registry.register(sql)

        result = registry.get_all()
        assert len(result) == 3

    def test_get_all_returns_in_insertion_order(self) -> None:
        """Test contributors are returned in insertion order."""
        registry = CliContributorRegistry()
        first = MockContributor("first", generator_count=0)
        second = MockContributor("second", generator_count=0)
        third = MockContributor("third", generator_count=0)

        registry.register(first)
        registry.register(second)
        registry.register(third)

        result = registry.get_all()
        assert result[0].contributor_id == "first"
        assert result[1].contributor_id == "second"
        assert result[2].contributor_id == "third"

    def test_is_runtime_checkable(self) -> None:
        """Test that contributors satisfy the protocol at runtime."""
        registry = CliContributorRegistry()
        contributor = MockContributor("test", generator_count=0)

        assert isinstance(contributor, CliContributorProtocol)

    def test_contributor_with_generators(self) -> None:
        """Test a contributor that provides generators."""
        registry = CliContributorRegistry()
        contributor = MockContributor("core", generator_count=3)

        registry.register(contributor)

        result = contributor.get_generators()
        assert len(result) == 3
        assert all(isinstance(g, GeneratorDefinition) for g in result)

    def test_multiple_contributors_with_generators(self) -> None:
        """Test multiple contributors each providing generators."""
        registry = CliContributorRegistry()
        core = MockContributor("core", generator_count=2)
        web = MockContributor("web", generator_count=3)

        registry.register(core)
        registry.register(web)

        core_gens = registry.get("core").get_generators()
        web_gens = registry.get("web").get_generators()

        assert len(core_gens) == 2
        assert len(web_gens) == 3
