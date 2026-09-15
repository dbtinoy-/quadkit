"""Guard execution mechanics: use_guards wrapper, execute_guards, require_admin."""

from __future__ import annotations

from typing import Any

import pytest
from starlette.requests import Request

from quadkit.result import Ok
from quadkit.web.security.guards import (
    AuthGuard,
    GuardRejection,
    PermissionGuard,
    RoleGuard,
    execute_guards,
    require_admin,
    use_guards,
)


class _FakeUser:
    def __init__(self, name: str = "u") -> None:
        self.name = name


class _FakeAuthorizer:
    def __init__(self, roles: set[str] | None = None, perms: set[str] | None = None):
        self.roles = roles or set()
        self.perms = perms or set()

    async def check_access(self, user: Any, roles: set[str]) -> bool:
        return bool(self.roles & roles)

    async def can(self, user: Any, action: str, resource: str) -> bool:
        return f"{resource}.{action}" in self.perms or action in self.perms


def _request(user: Any = None) -> Request:
    scope = {"type": "http", "method": "GET", "path": "/x", "headers": []}
    req = Request(scope)
    req.state.user = user
    return req


class _AuthOnly(AuthGuard):
    """Concrete AuthGuard (base is abstract)."""


class _RoleGuard(RoleGuard):
    pass


class _PermissionGuard(PermissionGuard):
    pass


class TestExecuteGuards:
    async def test_all_pass(self) -> None:
        result = await execute_guards([_AuthOnly()], _request(_FakeUser()))
        assert result == Ok(None)

    async def test_rejection(self) -> None:
        result = await execute_guards([_AuthOnly()], _request(None))
        assert result.is_err()
        rejection = result.unwrap_err()
        assert isinstance(rejection, GuardRejection)
        assert rejection.status_code == 403
        assert rejection.error == "Unauthorized"

    async def test_stops_at_first_failure(self) -> None:
        calls: list[str] = []

        class Recording(_AuthOnly):
            def __init__(self, name: str, allow: bool) -> None:
                self.name = name
                self.allow = allow

            async def can_activate(self, context: Any) -> bool:
                calls.append(self.name)
                return self.allow

        await execute_guards(
            [Recording("first", True), Recording("second", False)],
            _request(_FakeUser()),
        )
        assert calls == ["first", "second"]
        before = len(calls)
        await execute_guards(
            [Recording("a", False), Recording("b", True)],
            _request(_FakeUser()),
        )
        assert calls[before:] == ["a"]  # second guard never reached


class TestAuthGuard:
    async def test_authenticated(self) -> None:
        assert await _AuthOnly().can_activate(_request(_FakeUser())) is True
        assert await _AuthOnly().can_activate(_request(None)) is False


class TestRoleGuard:
    async def test_role_granted(self) -> None:
        g = _RoleGuard("admin", authorizer=_FakeAuthorizer(roles={"admin"}))
        assert await g.can_activate(_request(_FakeUser())) is True

    async def test_role_denied_and_anonymous(self) -> None:
        g = _RoleGuard("admin", authorizer=_FakeAuthorizer(roles={"user"}))
        assert await g.can_activate(_request(_FakeUser())) is False
        assert await g.can_activate(_request(None)) is False


class TestPermissionGuard:
    async def test_require_all(self) -> None:
        authorizer = _FakeAuthorizer(perms={"users.write", "users.read"})
        g = _PermissionGuard(
            "users.write", "users.read", authorizer=authorizer, require_all=True
        )
        assert await g.can_activate(_request(_FakeUser())) is True

        missing = _PermissionGuard(
            "users.write", "users.delete", authorizer=authorizer
        )
        assert await missing.can_activate(_request(_FakeUser())) is False

    async def test_require_any(self) -> None:
        authorizer = _FakeAuthorizer(perms={"users.write"})
        g = _PermissionGuard(
            "users.write", "users.delete", authorizer=authorizer, require_all=False
        )
        assert await g.can_activate(_request(_FakeUser())) is True

        none = _PermissionGuard(
            "a.x", "b.y", authorizer=authorizer, require_all=False
        )
        assert await none.can_activate(_request(_FakeUser())) is False

    async def test_no_permissions_fails_closed(self) -> None:
        g = _PermissionGuard(authorizer=_FakeAuthorizer(perms={"x.y"}))
        assert await g.can_activate(_request(_FakeUser())) is False

    async def test_authorizer_without_can_fails_closed(self) -> None:
        class NoCan:
            async def check_access(self, user: Any, roles: set[str]) -> bool:
                return True

        g = _PermissionGuard("x.y", authorizer=NoCan())
        assert await g.can_activate(_request(_FakeUser())) is False


class TestUseGuardsDecorator:
    async def test_guard_blocks_handler(self) -> None:
        @use_guards(_AuthOnly)
        async def handler(request: Request) -> str:
            return "secret"

        blocked = await handler(_request(None))
        assert blocked.status_code == 403
        assert blocked.body.startswith(b'{"error"')

    async def test_guard_allows_handler(self) -> None:
        @use_guards(_AuthOnly)
        async def handler(request: Request) -> str:
            return "secret"

        assert await handler(_request(_FakeUser())) == "secret"

    async def test_missing_request_raises(self) -> None:
        @use_guards(_AuthOnly)
        async def handler() -> str:  # no request parameter
            return "x"

        with pytest.raises(RuntimeError, match="requires request context"):
            await handler()

    def test_require_admin_authorizer_required(self) -> None:
        with pytest.raises(ValueError, match="authorizer"):

            @require_admin
            async def broken() -> None:
                return None

    async def test_require_admin_enforces_role(self) -> None:
        decorator = require_admin(authorizer=_FakeAuthorizer(roles={"admin"}))

        @decorator
        async def admin_only(request: Request) -> str:
            return "admin"

        assert await admin_only(_request(_FakeUser())) == "admin"
        denied = await admin_only(_request(None))
        assert denied.status_code == 403
