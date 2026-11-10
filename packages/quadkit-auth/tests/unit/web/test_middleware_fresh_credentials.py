"""A cached principal is never proof that credentials or an account are valid."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from pydantic import SecretStr
import pytest
from starlette.requests import Request

from quadkit.auth.authn.jwt import JWTTokenManager
from quadkit.auth.models.user import User
from quadkit.auth.web.middleware.auth import AuthMiddleware


def request(token: str) -> Request:
    return Request(
        {
            "type": "http",
            "path": "/private",
            "headers": [(b"authorization", f"Bearer {token}".encode())],
        }
    )


@pytest.fixture
def setup():
    user = User(user_id="fixture", email="local@example.invalid", roles=["admin"])
    manager = JWTTokenManager(
        current_key_id="local",
        keys={"local": SecretStr("public-local-fixture-key-at-least-32-characters")},
    )
    provider = SimpleNamespace(
        verify_token=manager.verify_token,
        get_user=AsyncMock(return_value=user),
        api_key_manager=None,
        session_manager=None,
        delegation_manager=None,
        cache_service=None,
    )
    middleware = AuthMiddleware(provider)
    token = manager.create_access_token(user)
    return middleware, provider, manager, user, token


@pytest.mark.parametrize("state", ["inactive", "deleted", "roles"])
async def test_repeated_token_uses_current_user_not_cached_snapshot(setup, state):
    middleware, provider, _, user, token = setup
    assert await middleware.authenticate_request(request(token)) is user
    current = (
        None
        if state == "deleted"
        else User(
            user_id=user.user_id,
            email=user.email,
            is_active=state != "inactive",
            roles=[],
        )
    )
    provider.get_user.return_value = current
    result = await middleware.authenticate_request(request(token))
    if state == "roles":
        assert result is current
        assert result.roles == []
    else:
        assert result is None


async def test_logout_rejects_previously_accepted_jwt(setup):
    middleware, _, manager, user, token = setup
    assert await middleware.authenticate_request(request(token)) is user
    assert (await manager.logout(token)).is_ok()
    assert await middleware.authenticate_request(request(token)) is None


async def test_expired_previously_accepted_jwt_is_rejected_without_cache_ttl_wait(
    setup,
):
    middleware, _, _, user, token = setup
    assert await middleware.authenticate_request(request(token)) is user
    with patch("jwt.api_jwt.datetime") as clock:
        clock.now.return_value = datetime.now(UTC) + timedelta(days=1)
        assert await middleware.authenticate_request(request(token)) is None


async def test_prefilled_legacy_identity_cache_cannot_authenticate_invalid_token(setup):
    middleware, _, _, user, _ = setup
    await middleware.token_cache.set("invalid", user)
    assert await middleware.authenticate_request(request("invalid")) is None


async def test_api_key_is_revalidated_on_every_request(setup):
    middleware, provider, _, user, _ = setup
    key = SimpleNamespace(user_id=user.user_id)
    provider.api_key_manager = SimpleNamespace(validate_key=AsyncMock(return_value=key))
    assert await middleware.authenticate_request(request("sk_local_fixture")) is user
    provider.api_key_manager.validate_key.return_value = None
    assert await middleware.authenticate_request(request("sk_local_fixture")) is None
    assert provider.api_key_manager.validate_key.await_count == 2
