"""Request authenticators must not accept inactive or malformed user records."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from quadkit.auth.authn.jwt import JWTTokenManager
from quadkit.auth.models.user import User
from quadkit.auth.web.middleware.api_key_authenticator import ApiKeyAuthenticator
from quadkit.auth.web.middleware.jwt_authenticator import JwtAuthenticator
from quadkit.auth.web.middleware.session_authenticator import SessionAuthenticator
from quadkit.validation import SecretStr


@pytest.fixture
def auth_context():
    user = User(user_id="user-1", email="active@example.test")
    manager = JWTTokenManager(
        current_key_id="test",
        keys={"test": SecretStr("test-only-secret-with-at-least-32-bytes")},
        required_audience="application",
    )
    provider = SimpleNamespace(
        verify_token=manager.verify_token,
        get_user=AsyncMock(return_value=user),
        api_key_manager=SimpleNamespace(
            validate_key=AsyncMock(return_value=SimpleNamespace(user_id=user.user_id))
        ),
        session_manager=SimpleNamespace(
            validate_session=AsyncMock(return_value=SimpleNamespace(user_id=user.user_id))
        ),
        delegation_manager=None,
    )
    token = manager.create_access_token(user)
    return provider, user, token


def request(token: str):
    return SimpleNamespace(
        headers={"Authorization": f"Bearer {token}"},
        cookies={"session_id": "valid-session"},
        query_params={},
        state=SimpleNamespace(),
        client=SimpleNamespace(host="127.0.0.1"),
    )


async def _authenticate(scheme, provider, token, req):
    if scheme == "jwt":
        return await JwtAuthenticator(provider).authenticate(req)
    if scheme == "api_key":
        return await ApiKeyAuthenticator(provider).authenticate("sk_valid", req)
    return await SessionAuthenticator(provider).authenticate(req)


@pytest.mark.parametrize("scheme", ["jwt", "api_key", "session"])
async def test_valid_credentials_follow_fresh_account_status(auth_context, scheme):
    provider, user, token = auth_context
    req = request(token)
    assert await _authenticate(scheme, provider, token, req) is user
    user.is_active = False
    req = request(token)
    assert await _authenticate(scheme, provider, token, req) is None
    assert not hasattr(req.state, "session")
    user.is_active = True
    assert await _authenticate(scheme, provider, token, request(token)) is user
    assert provider.get_user.await_count == 3


@pytest.mark.parametrize("scheme", ["jwt", "api_key", "session"])
@pytest.mark.parametrize("flag", [None, False, 0, 1, "true", "false"])
async def test_malformed_or_missing_active_flag_is_rejected(auth_context, scheme, flag):
    provider, _, token = auth_context
    provider.get_user.return_value = SimpleNamespace(user_id="user-1", is_active=flag)
    req = request(token)
    assert await _authenticate(scheme, provider, token, req) is None
    assert not hasattr(req.state, "session")


@pytest.mark.parametrize("scheme", ["jwt", "api_key", "session"])
async def test_missing_flag_is_rejected(auth_context, scheme):
    provider, _, token = auth_context
    provider.get_user.return_value = SimpleNamespace(user_id="user-1")
    req = request(token)
    assert await _authenticate(scheme, provider, token, req) is None
    assert not hasattr(req.state, "session")


@pytest.mark.parametrize("scheme", ["jwt", "api_key", "session"])
async def test_delegation_and_session_state_only_attached_for_active_user(auth_context, scheme):
    provider, user, token = auth_context
    delegations = [SimpleNamespace(id="delegate-1")]
    provider.delegation_manager = SimpleNamespace(
        get_active_delegations=AsyncMock(return_value=delegations)
    )
    user.is_active = False
    denied = request(token)
    assert await _authenticate(scheme, provider, token, denied) is None
    provider.delegation_manager.get_active_delegations.assert_not_awaited()
    assert not hasattr(denied.state, "session")
    assert not hasattr(denied.state, "delegations")

    user.is_active = True
    accepted = request(token)
    assert await _authenticate(scheme, provider, token, accepted) is user
    provider.delegation_manager.get_active_delegations.assert_awaited_once_with(user.user_id)
    assert accepted.state.delegations == delegations
    if scheme == "session":
        assert accepted.state.session.user_id == user.user_id
