"""Tests for contracts.cli.types — generator definition factory."""

from __future__ import annotations

import dataclasses

import pytest

from quadkit.contracts.cli.types import GeneratorDefinition


def test_make_derives_title_from_snake_case_name() -> None:
    d = GeneratorDefinition.make(
        "auth_guard",
        description="Guard",
        generator_path="pkg.mod:AuthGuardGenerator",
    )
    assert d.title == "Generate Auth Guard"
    assert d.name == "auth_guard"
    assert d.category == "general"
    assert d.default_output_dir == "src"


def test_make_derives_title_from_dashed_name() -> None:
    d = GeneratorDefinition.make(
        "document-repo",
        description="Repo",
        generator_path="x:Y",
    )
    assert d.title == "Generate Document Repo"


def test_make_explicit_title_overrides_derivation() -> None:
    d = GeneratorDefinition.make(
        "api_client",
        description="Client",
        generator_path="x:Y",
        title="Generate External API Client",
    )
    assert d.title == "Generate External API Client"


def test_make_carries_contributor_output_category_options() -> None:
    d = GeneratorDefinition.make(
        "seeder",
        description="Seeder",
        generator_path="pkg.mod:Seeder",
        output_dir="tests/unit",
        contributor="sql",
        category="database",
    )
    assert d.contributor == "sql"
    assert d.default_output_dir == "tests/unit"
    assert d.category == "database"
    assert d.options == ()


def test_make_result_is_frozen() -> None:
    d = GeneratorDefinition.make("x", description="d", generator_path="m:C")
    with pytest.raises(dataclasses.FrozenInstanceError):
        d.name = "y"  # type: ignore[misc]
