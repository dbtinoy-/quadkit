"""Tests for CoreCliContributor."""

from __future__ import annotations

import pytest

from quadkit.cli.contributors.base import BaseCliContributor
from quadkit.cli.contributors.core import CoreCliContributor
from quadkit.contracts.cli.types import GeneratorDefinition


class TestCoreCliContributor:
    """Tests for CoreCliContributor."""

    def test_is_subclass_of_base_contributor(self) -> None:
        """Test CoreCliContributor inherits from BaseCliContributor."""
        assert issubclass(CoreCliContributor, BaseCliContributor)

    def test_contributor_id_is_core(self) -> None:
        """Test contributor_id returns 'core'."""
        contributor = CoreCliContributor()
        assert contributor.contributor_id == "core"

    def test_get_generators_returns_list(self) -> None:
        """Test get_generators returns a list."""
        contributor = CoreCliContributor()
        result = contributor.get_generators()

        assert isinstance(result, list)

    def test_has_expected_number_of_generators(self) -> None:
        """Test that core contributor provides the expected number of generators."""
        contributor = CoreCliContributor()
        result = contributor.get_generators()

        assert len(result) == 2

    def test_all_generators_have_contributor_set_to_core(self) -> None:
        """Test all generator definitions have contributor='core'."""
        contributor = CoreCliContributor()
        result = contributor.get_generators()

        for gen in result:
            assert gen.contributor == "core"

    def test_all_generators_have_unique_names(self) -> None:
        """Test all generator names are unique."""
        contributor = CoreCliContributor()
        result = contributor.get_generators()

        names = [g.name for g in result]
        assert len(names) == len(set(names))

    def test_all_generators_have_titles(self) -> None:
        """Test all generators have non-empty titles."""
        contributor = CoreCliContributor()
        result = contributor.get_generators()

        for gen in result:
            assert gen.title
            assert gen.title.startswith("Generate ")

    def test_all_generators_have_descriptions(self) -> None:
        """Test all generators have non-empty descriptions."""
        contributor = CoreCliContributor()
        result = contributor.get_generators()

        for gen in result:
            assert gen.description

    def test_expected_core_generators_exist(self) -> None:
        """Test that expected core generators are present."""
        contributor = CoreCliContributor()
        result = contributor.get_generators()

        names = {g.name for g in result}

        expected = {"provider", "test"}

        assert expected == names
        assert "model" not in names
        assert "service" not in names
        assert "event" not in names
        assert "command" not in names
        assert "guard" not in names
        assert "query" not in names
        assert "controller" not in names
        assert "repository" not in names

    def test_moved_web_and_sql_generators_are_not_present(self) -> None:
        contributor = CoreCliContributor()
        names = {g.name for g in contributor.get_generators()}

        assert names.isdisjoint(
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

    def test_generator_definitions_are_valid(self) -> None:
        """Test all generator definitions are valid GeneratorDefinition instances."""
        contributor = CoreCliContributor()
        result = contributor.get_generators()

        for gen in result:
            assert isinstance(gen, GeneratorDefinition)
            assert gen.name
            assert gen.title
            assert gen.description

    def test_generator_titles_follow_pattern(self) -> None:
        """Test generator titles follow the expected pattern."""
        contributor = CoreCliContributor()
        result = contributor.get_generators()

        for gen in result:
            assert gen.title.startswith("Generate ")

    def test_multiple_instances_share_same_generators(self) -> None:
        """Test multiple CoreCliContributor instances return same generators."""
        contributor1 = CoreCliContributor()
        contributor2 = CoreCliContributor()

        result1 = contributor1.get_generators()
        result2 = contributor2.get_generators()

        assert len(result1) == len(result2)
        assert len(result1) == 2

    def test_all_generators_are_registered_in_registry(self) -> None:
        """Test that generators can be registered in registry."""
        from quadkit.cli.contributors.registry import CliContributorRegistry

        registry = CliContributorRegistry()
        contributor = CoreCliContributor()

        registry.register(contributor)

        assert registry.get("core") is not None
        assert len(registry.get_all()) == 1

    @pytest.mark.parametrize(
        "generator_name",
        [
            "provider",
            "test",
        ],
    )
    def test_specific_generators_exist(self, generator_name: str) -> None:
        """Test specific generators exist by name."""
        contributor = CoreCliContributor()
        result = contributor.get_generators()

        names = [g.name for g in result]
        assert generator_name in names, f"Missing generator: {generator_name}"
