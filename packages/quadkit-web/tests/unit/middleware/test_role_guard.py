"""Tests for the role guard middleware, its config, and its wiring."""

from __future__ import annotations

from typing import Any

import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from quadkit.contracts.exceptions.config import ConfigurationError
from quadkit.web.config import RoleGuardConfig, RoleGuardRuleConfig, WebConfig
from quadkit.web.integrations.auth import AuthIntegration
from quadkit.web.middleware.role_guard import (
    RoleGuardMiddleware,
    RoleGuardRule,
)

_MISSING = object()


class _FakeRoleResolver:
    """Resolver returning a fixed role set (None for unknown users)."""

    def __init__(self, roles: list[str] | None) -> None:
        self._roles = roles
        self.calls: list[str] = []

    async def resolve(self, user_id: str) -> list[str] | None:
        self.calls.append(user_id)
        return self._roles


class _SetIdentity:
    """Outer wrapper simulating the auth middleware's ``user_id`` in scope state."""

    def __init__(self, inner: Any, user_id: str | None) -> None:
        self.inner = inner
        self._user_id = user_id

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        scope.setdefault("state", {})["user_id"] = self._user_id
        await self.inner(scope, receive, send)


def _make_client(
    *,
    rules: list[RoleGuardRule],
    resolver: _FakeRoleResolver,
    user_id: Any = _MISSING,
) -> TestClient:
    """Build a TestClient exercising role rules over a trivial Starlette app."""

    async def homepage(request: Any) -> JSONResponse:
        return JSONResponse({"ok": True})

    inner = Starlette(
        routes=[
            Route("/", homepage),
            Route("/api/users", homepage),
            Route("/api/users/detail", homepage),
            Route("/api/admin/panel", homepage),
        ],
    )
    client_app: Any = RoleGuardMiddleware(inner, rules=rules, resolver=resolver)
    if user_id is not _MISSING:
        client_app = _SetIdentity(client_app, user_id)
    return TestClient(client_app, raise_server_exceptions=False)


class TestRoleGuardMiddleware:
    """Behavior matrix of the middleware itself."""

    def test_no_match_passes_through(self) -> None:
        resolver = _FakeRoleResolver(["user"])
        client = _make_client(
            rules=[RoleGuardRule(path="/api/users", roles=["admin"])],
            resolver=resolver,
            user_id="u1",
        )

        response = client.get("/")

        assert response.status_code == 200
        assert resolver.calls == []

    def test_exact_match_denies_non_intersecting_roles(self) -> None:
        resolver = _FakeRoleResolver(["user"])
        client = _make_client(
            rules=[RoleGuardRule(path="/api/users", roles=["admin"])],
            resolver=resolver,
            user_id="u1",
        )

        response = client.get("/api/users")

        assert response.status_code == 403
        assert response.json() == {"error": "Forbidden"}
        assert resolver.calls == ["u1"]

    def test_exact_match_allows_intersecting_roles(self) -> None:
        resolver = _FakeRoleResolver(["user", "admin"])
        client = _make_client(
            rules=[RoleGuardRule(path="/api/users", roles=["admin"])],
            resolver=resolver,
            user_id="u1",
        )

        response = client.get("/api/users")

        assert response.status_code == 200
        assert response.json() == {"ok": True}

    def test_exact_rule_does_not_match_subpaths(self) -> None:
        resolver = _FakeRoleResolver(["user"])
        client = _make_client(
            rules=[RoleGuardRule(path="/api/users", roles=["admin"])],
            resolver=resolver,
            user_id="u1",
        )

        response = client.get("/api/users/detail")

        assert response.status_code == 200
        assert resolver.calls == []

    def test_prefix_rule_matches_subpaths_and_prefix_itself(self) -> None:
        resolver = _FakeRoleResolver(["user"])
        client = _make_client(
            rules=[RoleGuardRule(path="/api/admin/**", roles=["admin"])],
            resolver=resolver,
            user_id="u1",
        )

        assert client.get("/api/admin/panel").status_code == 403
        assert client.get("/api/admin").status_code == 403

    def test_prefix_rule_allows_intersecting_roles(self) -> None:
        resolver = _FakeRoleResolver(["admin"])
        client = _make_client(
            rules=[RoleGuardRule(path="/api/admin/**", roles=["admin"])],
            resolver=resolver,
            user_id="u1",
        )

        assert client.get("/api/admin/panel").status_code == 200

    def test_missing_identity_returns_401(self) -> None:
        resolver = _FakeRoleResolver(["user"])
        client = _make_client(
            rules=[RoleGuardRule(path="/api/users", roles=["admin"])],
            resolver=resolver,
            user_id=None,
        )

        response = client.get("/api/users")

        assert response.status_code == 401
        assert response.json() == {"error": "Unauthorized"}
        assert resolver.calls == []

    def test_resolver_none_returns_403(self) -> None:
        resolver = _FakeRoleResolver(None)
        client = _make_client(
            rules=[RoleGuardRule(path="/api/users", roles=["admin"])],
            resolver=resolver,
            user_id="u1",
        )

        response = client.get("/api/users")

        assert response.status_code == 403
        assert response.json() == {"error": "Forbidden"}

    def test_first_rule_wins(self) -> None:
        resolver = _FakeRoleResolver(["viewer"])
        client = _make_client(
            rules=[
                RoleGuardRule(path="/api/users", roles=["viewer"]),
                RoleGuardRule(path="/api/users", roles=["admin"]),
            ],
            resolver=resolver,
            user_id="u1",
        )

        response = client.get("/api/users")

        assert response.status_code == 200

    def test_non_http_scope_passes_through(self) -> None:
        import asyncio

        resolver = _FakeRoleResolver(["admin"])
        inner_calls = []

        async def inner(scope: Any, receive: Any, send: Any) -> None:
            inner_calls.append(scope["type"])

        async def no_body() -> bytes:
            return b""

        async def no_send(message: Any) -> None:
            return None

        guard = RoleGuardMiddleware(
            inner,
            rules=[RoleGuardRule(path="/api/users", roles=["admin"])],
            resolver=resolver,
        )
        scope: dict[str, Any] = {
            "type": "websocket",
            "path": "/api/users",
            "headers": [],
        }

        asyncio.run(guard(scope, no_body, no_send))

        assert inner_calls == ["websocket"]
        assert resolver.calls == []


class TestRoleGuardConfig:
    """WebConfig parses ``web.role_guard`` from the yaml section."""

    def test_rules_parse_from_nested_web_config(self) -> None:
        config = WebConfig(
            role_guard=RoleGuardConfig(
                rules=[RoleGuardRuleConfig(path="/api/users", roles=["admin"])],
            ),
        )

        assert config.role_guard.enabled
        assert config.role_guard.rules[0].path == "/api/users"
        assert config.role_guard.rules[0].roles == ["admin"]

    def test_disabled_by_default(self) -> None:
        config = WebConfig()

        assert not config.role_guard.enabled
        assert config.role_guard.rules == []


class TestRoleGuardWiring:
    """AuthIntegration registers the guard after auth, failing fast."""

    class _FakeContainer:
        def __init__(self, resolver: Any | None) -> None:
            self._resolver = resolver

        async def resolve(self, service_type: Any) -> Any:
            if self._resolver is None:
                raise LookupError("not registered")
            return self._resolver

    class _FakeWebConfig:
        auth_exclude_paths = ["/health"]
        enable_identity_resolution = False

        def __init__(self, rules: list[Any]) -> None:
            self.role_guard = RoleGuardConfig(rules=rules)

    def _middleware_classes(self, app: Starlette) -> list[str]:
        return [m.cls.__name__ for m in app.user_middleware]

    @pytest.mark.asyncio
    async def test_no_rules_adds_nothing(self) -> None:
        container = self._FakeContainer(None)
        app = Starlette()

        await AuthIntegration._add_role_guard(app, container, self._FakeWebConfig([]))

        assert "RoleGuardMiddleware" not in self._middleware_classes(app)

    @pytest.mark.asyncio
    async def test_rules_with_resolver_register_guard(self) -> None:
        resolver = _FakeRoleResolver(["admin"])
        container = self._FakeContainer(resolver)
        app = Starlette()

        await AuthIntegration._add_role_guard(
            app,
            container,
            self._FakeWebConfig(
                [RoleGuardRuleConfig(path="/api/users", roles=["admin"])],
            ),
        )

        guard = next(
            m for m in app.user_middleware if m.cls.__name__ == "RoleGuardMiddleware"
        )
        assert guard.kwargs["resolver"] is resolver
        assert guard.kwargs["rules"][0].path == "/api/users"

    @pytest.mark.asyncio
    async def test_guard_registered_after_auth_middleware(self) -> None:
        """The guard must run after auth so ``user_id`` is in scope state."""
        from quadkit.web.middleware.auth import AuthenticationMiddleware

        resolver = _FakeRoleResolver(["admin"])
        container = self._FakeContainer(resolver)
        app = Starlette()
        app.add_middleware(AuthenticationMiddleware, authenticators=[])

        await AuthIntegration._add_role_guard(
            app,
            container,
            self._FakeWebConfig(
                [RoleGuardRuleConfig(path="/api/users", roles=["admin"])],
            ),
        )

        classes = self._middleware_classes(app)
        assert classes.index("RoleGuardMiddleware") > classes.index(
            "AuthenticationMiddleware"
        )

    @pytest.mark.asyncio
    async def test_rules_without_resolver_fail_fast(self) -> None:
        container = self._FakeContainer(None)
        app = Starlette()

        with pytest.raises(ConfigurationError):
            await AuthIntegration._add_role_guard(
                app,
                container,
                self._FakeWebConfig(
                    [RoleGuardRuleConfig(path="/api/users", roles=["admin"])],
                ),
            )
