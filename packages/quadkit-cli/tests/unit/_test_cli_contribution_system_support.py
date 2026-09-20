"""Shared fixtures/stubs for test_cli_contribution_system tests."""

from __future__ import annotations

from quadkit.contracts.cli.types import GeneratorDefinition


def _make_gen_def(name: str, contributor: str = "test") -> GeneratorDefinition:
    return GeneratorDefinition(
        name=name,
        title=name.capitalize(),
        description=f"Generate {name}",
        contributor=contributor,
        generator_path="tests.fake:FakeGenerator",
    )


class _FakeContributor:
    """Minimal CliContributorProtocol-compatible stub."""

    def __init__(self, contributor_id: str, gen_names: list[str]) -> None:
        self._contributor_id = contributor_id
        self._gen_names = gen_names

    @property
    def contributor_id(self) -> str:
        return self._contributor_id

    def get_generators(self) -> list[GeneratorDefinition]:
        return [_make_gen_def(n, self._contributor_id) for n in self._gen_names]
