"""Regression tests for AuthenticationMiddleware DomainModel normalization and exclusions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.testclient import TestClient

from quadkit.domain import DomainModel
from quadkit.web.middleware.auth import AuthenticationMiddleware


@dataclass(init=False, eq=False, kw_only=True)
class _AuthUser(DomainModel):
    user_id: UUID
    email: str


async def _echo_user(scope: Any, receive: Any, send: Any) -> None:
    req = Request(scope)
    user = getattr(req.state, "user", None)
    safe_user = (
        {k: str(v) if isinstance(v, UUID) else v for k, v in user.items()}
        if isinstance(user, dict)
        else user
    )
    await JSONResponse({"user": safe_user})(scope, receive, send)


def test_domain_model_user_normalized_before_identity_resolver() -> None:
    """DomainModel user returned by authenticator is normalized to dict for identity_resolver."""
    ext_uuid = UUID("11111111-1111-1111-1111-111111111111")
    internal_uuid = UUID("22222222-2222-2222-2222-222222222222")
    domain_user = _AuthUser(user_id=ext_uuid, email="maria@example.com")

    auth = MagicMock()
    auth.authenticate = AsyncMock(return_value=domain_user)

    resolver = MagicMock()
    resolver.resolve_user_id = AsyncMock(return_value=internal_uuid)

    mw = AuthenticationMiddleware(
        _echo_user,
        authenticators=[auth],
        enable_identity_resolution=True,
        identity_resolver=resolver,
    )
    client = TestClient(mw)
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 200
    payload = resp.json()["user"]
    assert payload["id"] == str(internal_uuid)
    assert payload["email"] == "maria@example.com"


def test_root_exclusion_does_not_prefix_match_all_paths() -> None:
    """Excluding '/' allows exact '/' without turning '/api/v1/secret' public."""
    auth = MagicMock()
    auth.authenticate = AsyncMock(return_value=None)

    mw = AuthenticationMiddleware(
        _echo_user,
        authenticators=[auth],
        exclude_paths=["/"],
    )
    client = TestClient(mw)
    assert client.get("/").status_code == 200
    assert client.get("/api/v1/secret").status_code == 401


def test_method_scoped_exclusion_allows_get_and_blocks_post() -> None:
    """'GET /api/v1/media/' allows unauthenticated GET while requiring auth on POST."""
    auth = MagicMock()
    auth.authenticate = AsyncMock(return_value=None)

    mw = AuthenticationMiddleware(
        _echo_user,
        authenticators=[auth],
        exclude_paths=["GET /api/v1/media/", "HEAD /api/v1/media/"],
    )
    client = TestClient(mw)
    assert client.get("/api/v1/media/avatar.png").status_code == 200
    assert client.head("/api/v1/media/avatar.png").status_code == 200
    assert client.post("/api/v1/media/upload").status_code == 401
