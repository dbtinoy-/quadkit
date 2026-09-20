"""Tests for BaseCliContributor."""

from __future__ import annotations

import pytest

from quadkit.cli.contributors.base import BaseCliContributor
from quadkit.contracts.cli.protocols import CliContributorProtocol
from quadkit.contracts.cli.types import GeneratorDefinition


class MinimalContributor(BaseCliContributor):
    """Minimal implementation of BaseCliContributor."""

    @property
    def contributor_id(self) -> str:
        return "minimal"


class ContributorWithGenerators(BaseCliContributor):
    """Contributor that provides generators."""

    @property
    def contributor_id(self) -> str:
        return "generators"

    def get_generators(self) -> list[GeneratorDefinition]:
        return [
            GeneratorDefinition(
                name="test-gen",
                title="Generate Test",
                description="A test generator",
                contributor="generators",
                generator_path="tests.fake:FakeGenerator",
            )
        ]


class TestBaseCliContributor:
    """Tests for BaseCliContributor."""

    def test_contributor_id_property_required(self) -> None:
        """Test that contributor_id must be implemented in subclass."""

        class MissingId(BaseCliContributor):
            pass

        with pytest.raises(NotImplementedError):
            _ = MissingId().contributor_id

    def test_default_get_generators_returns_empty_list(self) -> None:
        """Test default get_generators returns empty list."""
        contributor = MinimalContributor()

        result = contributor.get_generators()
        assert result == []

    def test_subclass_can_override_get_generators(self) -> None:
        """Test subclass can provide custom generators."""
        contributor = ContributorWithGenerators()

        result = contributor.get_generators()
        assert len(result) == 1
        assert result[0].name == "test-gen"

    def test_base_contributor_get_schema_setup_defaults_empty(self) -> None:
        """Test default get_schema_setup returns empty list."""
        assert MinimalContributor().get_schema_setup() == []

    def test_satisfies_cli_contributor_protocol(self) -> None:
        """Test that BaseCliContributor satisfies CliContributorProtocol."""
        contributor = MinimalContributor()

        assert isinstance(contributor, CliContributorProtocol)

    def test_contributor_id_is_unique_string(self) -> None:
        """Test contributor_id returns a string."""
        contributor = MinimalContributor()

        assert isinstance(contributor.contributor_id, str)
        assert contributor.contributor_id == "minimal"

    def test_multiple_contributors_have_different_ids(self) -> None:
        """Test different subclasses can have different IDs."""
        minimal = MinimalContributor()
        with_generators = ContributorWithGenerators()

        assert minimal.contributor_id != with_generators.contributor_id
        assert minimal.contributor_id == "minimal"
        assert with_generators.contributor_id == "generators"

    def test_get_generators_returns_list_type(self) -> None:
        """Test get_generators returns a list."""
        contributor = MinimalContributor()

        result = contributor.get_generators()
        assert isinstance(result, list)

    def test_generator_list_can_be_empty(self) -> None:
        """Test contributor can return empty generator list."""
        contributor = MinimalContributor()

        result = contributor.get_generators()
        assert len(result) == 0

    def test_generator_list_can_have_multiple_items(self) -> None:
        """Test contributor can provide multiple generators."""

        class MultiGenerator(BaseCliContributor):
            @property
            def contributor_id(self) -> str:
                return "multi"

            def get_generators(self) -> list[GeneratorDefinition]:
                return [
                    GeneratorDefinition(
                        name=f"gen-{i}",
                        title=f"Gen {i}",
                        description=f"Generator {i}",
                        contributor="multi",
                        generator_path="tests.fake:FakeGenerator",
                    )
                    for i in range(5)
                ]

        contributor = MultiGenerator()
        result = contributor.get_generators()

        assert len(result) == 5
        assert result[0].name == "gen-0"
        assert result[4].name == "gen-4"
