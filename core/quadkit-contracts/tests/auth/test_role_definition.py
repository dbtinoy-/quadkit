"""RoleDefinition — the single role model (spec D2)."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from quadkit.contracts.auth import RoleDefinition


def test_defaults() -> None:
    role = RoleDefinition(name="editor")
    assert role.description == ""
    assert role.permissions == []
    assert role.inherits == []
    assert role.is_system is False


def test_scoped_permission_strings_survive() -> None:
    role = RoleDefinition(
        name="manager",
        permissions=["users.read:team", "users.write", "users.delete:all"],
    )
    assert role.permissions == ["users.read:team", "users.write", "users.delete:all"]


def test_is_system_roundtrip() -> None:
    role = RoleDefinition(name="superadmin", is_system=True)
    assert role.is_system is True


def test_frozen() -> None:
    role = RoleDefinition(name="locked")
    with pytest.raises(FrozenInstanceError):
        role.description = "mutable"