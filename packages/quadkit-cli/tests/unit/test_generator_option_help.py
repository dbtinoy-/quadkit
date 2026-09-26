"""Tests for declared generator options on contributor definitions."""

from __future__ import annotations

import pytest

from quadkit.cli.assembly.assembler import _build_help_text
from quadkit.contracts.cli.types import GeneratorDefinition, GeneratorOption
from quadkit.sql.cli.contributor import SqlCliContributor
from quadkit.web.cli.contributor import WebCliContributor


@pytest.mark.parametrize(
    ("contributor_cls", "name", "expected_option_names"),
    [
        (SqlCliContributor, "repository", ["fields"]),
        (SqlCliContributor, "filter", ["fields", "exception_type"]),
        (SqlCliContributor, "seeder", ["fields"]),
        (SqlCliContributor, "health", ["critical"]),
        (WebCliContributor, "controller", ["fields", "path", "doc"]),
        (WebCliContributor, "resource", ["fields"]),
    ],
)
def test_definitions_declare_expected_options(
    contributor_cls: type,
    name: str,
    expected_option_names: list[str],
) -> None:
    definitions = {d.name: d for d in contributor_cls().get_generators()}
    option_names = [o.name for o in definitions[name].options]
    assert option_names == expected_option_names


def test_help_text_appends_declared_options() -> None:
    definition = GeneratorDefinition(
        name="demo",
        title="Demo",
        description="Generate a demo",
        contributor="core",
        generator_path="x:Y",
        options=(
            GeneratorOption(name="path", type_hint="str", description="Base path"),
            GeneratorOption(
                name="force_like",
                type_hint="bool",
                default=True,
                description="Flag it",
            ),
        ),
    )
    help_text = _build_help_text(definition)
    assert help_text.startswith("Generate a demo")
    assert "--path (str) Base path" in help_text
    assert "--force_like (bool) [default: True] Flag it" in help_text


def test_help_text_without_options_is_plain_description() -> None:
    definition = GeneratorDefinition(
        name="bare",
        title="Bare",
        description="Generate nothing",
        contributor="core",
        generator_path="x:Y",
    )
    assert _build_help_text(definition) == "Generate nothing"
