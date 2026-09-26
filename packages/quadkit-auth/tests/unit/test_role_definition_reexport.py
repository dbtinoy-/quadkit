"""One RoleDefinition — auth re-exports contracts (AGENTS.md §2.6)."""

from __future__ import annotations

from quadkit.auth.types import RoleDefinition
from quadkit.contracts.auth import RoleDefinition as ContractsRole


def test_single_definition() -> None:
    assert RoleDefinition is ContractsRole
    assert RoleDefinition(name="x").permissions == []