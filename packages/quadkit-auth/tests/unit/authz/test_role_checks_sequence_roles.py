"""Role checks accept the sequence shapes a principal actually uses (AUTHZ-1).

The unit tests for the parsers cover the container types; this covers the
claim the entry made, one level up: `AuthorizationService.has_any_role` with a
user whose `roles` is a tuple. The tuple matched no parser, so the registry
stringified the whole container into a single bogus role name — the checks
failed while the 403 message blamed the user for lacking a role they held.
"""

from __future__ import annotations

from typing import Any

import pytest

from quadkit.auth.authz.service import AuthorizationService


class _Principal:
    """Minimal principal: the attributes the check mixin reads."""

    def __init__(self, roles: Any) -> None:
        self.roles = roles
        self.permissions: tuple[str, ...] = ()
        self.is_superuser = False


def _service() -> AuthorizationService:
    service = AuthorizationService()
    service.set_roles({"demo_role": {"permissions": ["orders:read"]}})
    return service


@pytest.mark.parametrize(
    "roles",
    [
        ["demo_role"],
        ("demo_role",),
        frozenset({"demo_role"}),
        {"demo_role"},
    ],
    ids=["list", "tuple", "frozenset", "set"],
)
def test_a_sequence_of_roles_authorizes(roles: Any) -> None:
    assert _service().has_any_role(_Principal(roles), ["demo_role"]) is True


def test_a_role_the_principal_does_not_hold_still_fails() -> None:
    """Widening the parser must not widen what it means to be authorized."""
    assert _service().has_any_role(_Principal(("other_role",)), ["demo_role"]) is False
    assert _service().has_any_role(_Principal(()), ["demo_role"]) is False
    assert _service().has_any_role(None, ["demo_role"]) is False
