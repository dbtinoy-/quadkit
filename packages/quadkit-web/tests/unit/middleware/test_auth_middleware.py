"""Tests for middleware/auth.py — AuthenticationMiddleware."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from starlette.responses import PlainTextResponse
from starlette.testclient import TestClient

from quadkit.web.middleware.auth import AuthenticationMiddleware


async def _plain_inner(scope, receive, send) -> None:
    response = PlainTextResponse("ok")
    await response(scope, receive, send)


def _make_authenticator(user: dict | None) -> MagicMock:
    auth = MagicMock()
    auth.authenticate = AsyncMock(return_value=user)
    return auth


class TestAuthenticationMiddlewareInit:
    def test_defaults(self) -> None:
        mw = AuthenticationMiddleware(_plain_inner)
        assert mw.authenticators == []
        assert mw.authorizer is None
        assert mw.exclude_paths == []
        assert mw.enable_identity_resolution is False
        assert mw.identity_resolver is None

    def test_with_all_params(self) -> None:
        auth = _make_authenticator(None)
        authorizer = MagicMock()
        resolver = MagicMock()
        mw = AuthenticationMiddleware(
            _plain_inner,
            authenticators=[auth],
            authorizer=authorizer,
            exclude_paths=["/health"],
            enable_identity_resolution=True,
            identity_resolver=resolver,
        )
        assert mw.authenticators == [auth]
        assert mw.authorizer is authorizer
        assert "/health" in mw.exclude_paths
        assert mw.enable_identity_resolution is True
        assert mw.identity_resolver is resolver


class TestAuthenticationMiddlewareCall:
    def test_no_authenticators_lets_request_through(self) -> None:
        """When no authenticators are configured, all requests pass through."""
        mw = AuthenticationMiddleware(_plain_inner)
        client = TestClient(mw)
        response = client.get("/api/data")
        assert response.status_code == 200
        assert response.text == "ok"

    def test_excluded_path_passes_through(self) -> None:
        auth = _make_authenticator(None)  # Always returns None (unauthenticated)
        mw = AuthenticationMiddleware(
            _plain_inner,
            authenticators=[auth],
            exclude_paths=["/health"],
        )
        client = TestClient(mw)
        response = client.get("/health")
        assert response.status_code == 200

    def test_excluded_path_prefix_passes_through(self) -> None:
        auth = _make_authenticator(None)
        mw = AuthenticationMiddleware(
            _plain_inner,
            authenticators=[auth],
            exclude_paths=["/public"],
        )
        client = TestClient(mw)
        response = client.get("/public/images/logo.png")
        assert response.status_code == 200

    def test_unauthenticated_returns_401(self) -> None:
        auth = _make_authenticator(None)  # Returns None: auth fails
        mw = AuthenticationMiddleware(
            _plain_inner,
            authenticators=[auth],
        )
        client = TestClient(mw, raise_server_exceptions=False)
        response = client.get("/api/secret")
        assert response.status_code == 401

    def test_authenticated_passes_through(self) -> None:
        user = {"id": "user-1", "email": "test@example.com"}
        auth = _make_authenticator(user)
        mw = AuthenticationMiddleware(
            _plain_inner,
            authenticators=[auth],
        )
        client = TestClient(mw)
        response = client.get("/api/data")
        assert response.status_code == 200
        assert response.text == "ok"

    def test_first_successful_authenticator_wins(self) -> None:
        auth1 = _make_authenticator(None)  # Fails
        user = {"id": "user-2"}
        auth2 = _make_authenticator(user)  # Succeeds
        mw = AuthenticationMiddleware(
            _plain_inner,
            authenticators=[auth1, auth2],
        )
        client = TestClient(mw)
        response = client.get("/api/data")
        assert response.status_code == 200

    def test_user_stored_in_scope_extensions(self) -> None:
        user = {"id": "user-1"}
        auth = _make_authenticator(user)

        scope_captures = {}

        async def capturing_inner(scope, receive, send) -> None:
            scope_captures["user"] = scope.get("extensions", {}).get("user")
            response = PlainTextResponse("ok")
            await response(scope, receive, send)

        mw = AuthenticationMiddleware(
            capturing_inner,
            authenticators=[auth],
        )
        client = TestClient(mw)
        client.get("/api/data")
        assert scope_captures["user"] == user

    @pytest.mark.asyncio
    async def test_non_http_scope_passes_through(self) -> None:
        called = []

        async def inner(scope, receive, send) -> None:
            called.append(scope["type"])

        mw = AuthenticationMiddleware(inner, authenticators=[_make_authenticator(None)])
        await mw({"type": "websocket"}, None, None)
        assert "websocket" in called

    def test_identity_resolution_updates_user_id(self) -> None:
        user = {"id": "oauth-ext-123"}
        auth = _make_authenticator(user)
        resolver = MagicMock()
        resolver.resolve_user_id = AsyncMock(return_value="internal-uuid-456")

        scope_captures = {}

        async def capturing_inner(scope, receive, send) -> None:
            ext = scope.get("extensions", {})
            scope_captures["user_id"] = ext.get("user_id")
            scope_captures["user"] = ext.get("user")
            response = PlainTextResponse("ok")
            await response(scope, receive, send)

        mw = AuthenticationMiddleware(
            capturing_inner,
            authenticators=[auth],
            enable_identity_resolution=True,
            identity_resolver=resolver,
        )
        client = TestClient(mw)
        client.get("/api/data")
        # Identity resolution should have updated user_id
        assert scope_captures["user_id"] == "internal-uuid-456"


@pytest.mark.parametrize("malformed", [True, False, 42, object()])
def test_malformed_result_is_not_authenticated(malformed) -> None:
    called = []

    async def inner(scope, receive, send) -> None:
        called.append(True)
        await _plain_inner(scope, receive, send)

    auth = _make_authenticator(malformed)
    response = TestClient(AuthenticationMiddleware(inner, authenticators=[auth])).get(
        "/private"
    )
    assert response.status_code == 401
    assert called == []


def test_malformed_result_does_not_prevent_later_authenticator() -> None:
    first = _make_authenticator(True)
    second = _make_authenticator({"id": "valid"})
    response = TestClient(
        AuthenticationMiddleware(_plain_inner, authenticators=[first, second])
    ).get("/private")
    assert response.status_code == 200
    second.authenticate.assert_awaited_once()


def test_malformed_result_on_excluded_path_remains_anonymous() -> None:
    captured = []

    async def inner(scope, receive, send) -> None:
        captured.append(scope["state"]["user"])
        await _plain_inner(scope, receive, send)

    auth = _make_authenticator(True)
    response = TestClient(
        AuthenticationMiddleware(
            inner, authenticators=[auth], exclude_paths=["/health"]
        )
    ).get("/health")
    assert response.status_code == 200
    assert captured == [None]


def test_non_mapping_model_dump_is_not_authenticated() -> None:
    user = MagicMock()
    user.model_dump.return_value = True
    auth = _make_authenticator(user)
    response = TestClient(
        AuthenticationMiddleware(_plain_inner, authenticators=[auth])
    ).get("/private")
    assert response.status_code == 401


@pytest.mark.parametrize("malformed", [{}, [], type("Empty", (), {})()])
def test_empty_identity_is_not_authenticated(malformed) -> None:
    called = []

    async def inner(scope, receive, send) -> None:
        called.append(True)
        await _plain_inner(scope, receive, send)

    auth = _make_authenticator(malformed)
    response = TestClient(AuthenticationMiddleware(inner, authenticators=[auth])).get(
        "/private"
    )
    assert response.status_code == 401
    assert called == []


def test_empty_identity_does_not_prevent_later_authenticator() -> None:
    first = _make_authenticator({})
    second = _make_authenticator({"id": "valid"})
    response = TestClient(
        AuthenticationMiddleware(_plain_inner, authenticators=[first, second])
    ).get("/private")
    assert response.status_code == 200
    second.authenticate.assert_awaited_once()


def test_empty_model_dump_is_not_authenticated() -> None:
    user = MagicMock()
    user.model_dump.return_value = {}
    auth = _make_authenticator(user)
    response = TestClient(
        AuthenticationMiddleware(_plain_inner, authenticators=[auth])
    ).get("/private")
    assert response.status_code == 401
