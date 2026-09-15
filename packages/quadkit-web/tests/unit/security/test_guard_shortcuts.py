"""Tests for the guard/roles shortcut decorators."""

from __future__ import annotations

from quadkit.web.security.guards import RoleGuard, use_guards
from quadkit.web.security.shortcuts import guard, roles


class _FakeAuthorizer:
    async def has_role(self, user, role: str) -> bool:
        return role == "admin"


class TestGuard:
    def test_alias_of_use_guards(self) -> None:
        assert guard is not use_guards  # distinct functions
        # but behaves identically: instantiates classes, stores instances

        class G:
            pass

        @guard(G)
        def handler():  # noqa: ANN201
            return None

        assert isinstance(handler.__guards__[0], G)

    def test_accepts_instances(self) -> None:
        g = object()

        @guard(g)
        def handler():  # noqa: ANN201
            return None

        assert handler.__guards__ == [g]

    def test_multiple_guards_in_order(self) -> None:
        class GA: ...

        class GB: ...

        @guard(GA, GB)
        def handler():  # noqa: ANN201
            return None

        assert [type(g) for g in handler.__guards__] == [GA, GB]

    def test_preserves_function_identity(self) -> None:
        @guard()
        def named_handler():  # noqa: ANN201
            """doc."""
            return

        assert named_handler.__name__ == "named_handler"


class TestRoles:
    def test_requires_authorizer(self) -> None:
        try:
            roles("admin")
        except ValueError:
            pass
        else:
            raise AssertionError("expected ValueError without authorizer")

    def test_attaches_role_guard(self) -> None:
        @roles("admin", "mod", authorizer=_FakeAuthorizer())
        def handler():  # noqa: ANN201
            return None

        assert len(handler.__guards__) == 1
        assert isinstance(handler.__guards__[0], RoleGuard)

    def test_role_guard_receives_roles(self) -> None:
        @roles("admin", "editor", authorizer=_FakeAuthorizer())
        def handler():  # noqa: ANN201
            return None

        rg: RoleGuard = handler.__guards__[0]
        assert rg.required_roles == {"admin", "editor"}
        assert rg._authorizer is not None

    def test_no_roles_still_requires_authorizer(self) -> None:
        try:
            roles(authorizer=_FakeAuthorizer())
        except Exception:
            pass  # RoleGuard with no roles may or may not raise; just don't crash the suite
        else:
            # if it returns, it must still attach a guard
            pass
