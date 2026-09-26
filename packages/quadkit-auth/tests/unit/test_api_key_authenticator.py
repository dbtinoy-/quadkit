"""Tests for APIKeyAuthenticator (Task G4-A6.1)."""

from __future__ import annotations

import pytest

from quadkit.auth.authn.api_key import APIKeyAuthenticator, APIKeyConfig
from quadkit.auth.exceptions import AuthenticationError
from quadkit.auth.models.user import User


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(user_id: str = "u1", email: str = "alice@example.com") -> User:
    return User(
        user_id=user_id,
        email=email,
        name="Alice",
        roles=["user"],
    )


# ---------------------------------------------------------------------------
# APIKeyConfig
# ---------------------------------------------------------------------------


class TestAPIKeyConfig:
    def test_defaults(self) -> None:
        user = _make_user()
        config = APIKeyConfig(lookup={"sk_test_abc": user})
        assert config.header_name == "X-API-Key"
        assert config.query_param == "api_key"

    def test_custom_header_and_param(self) -> None:
        config = APIKeyConfig(
            lookup={},
            header_name="Authorization",
            query_param="token",
        )
        assert config.header_name == "Authorization"
        assert config.query_param == "token"

    def test_dict_lookup_flagged(self) -> None:
        config = APIKeyConfig(lookup={"k": _make_user()})
        assert config._lookup_is_dict is True

    def test_callable_lookup_flagged(self) -> None:
        async def fake_lookup(key: str) -> User | None:
            return None

        config = APIKeyConfig(lookup=fake_lookup)
        assert config._lookup_is_dict is False


# ---------------------------------------------------------------------------
# APIKeyAuthenticator — header extraction
# ---------------------------------------------------------------------------


class TestAPIKeyAuthenticatorHeaderExtraction:
    @pytest.mark.asyncio
    async def test_extracts_from_default_header(self) -> None:
        user = _make_user()
        auth = APIKeyAuthenticator(APIKeyConfig(lookup={"sk_live_xyz": user}))

        result = await auth.authenticate(
            {"headers": {"X-API-Key": "sk_live_xyz"}, "query_params": {}}
        )

        assert result.is_ok()
        assert result.unwrap() is user

    @pytest.mark.asyncio
    async def test_header_lookup_is_case_insensitive(self) -> None:
        user = _make_user()
        auth = APIKeyAuthenticator(APIKeyConfig(lookup={"sk_live_xyz": user}))

        result = await auth.authenticate(
            {"headers": {"x-api-key": "sk_live_xyz"}, "query_params": {}}
        )

        assert result.is_ok()

    @pytest.mark.asyncio
    async def test_falls_back_to_query_param(self) -> None:
        user = _make_user()
        auth = APIKeyAuthenticator(APIKeyConfig(lookup={"sk_q_abc": user}))

        result = await auth.authenticate(
            {"headers": {}, "query_params": {"api_key": "sk_q_abc"}}
        )

        assert result.is_ok()
        assert result.unwrap() is user

    @pytest.mark.asyncio
    async def test_header_takes_precedence_over_query_param(self) -> None:
        user_a = _make_user("u1")
        user_b = _make_user("u2")
        auth = APIKeyAuthenticator(
            APIKeyConfig(lookup={"header_key": user_a, "query_key": user_b})
        )

        result = await auth.authenticate(
            {
                "headers": {"X-API-Key": "header_key"},
                "query_params": {"api_key": "query_key"},
            }
        )

        assert result.is_ok()
        assert result.unwrap() is user_a

    @pytest.mark.asyncio
    async def test_missing_key_returns_err(self) -> None:
        auth = APIKeyAuthenticator(APIKeyConfig(lookup={}))

        result = await auth.authenticate({"headers": {}, "query_params": {}})

        assert result.is_err()
        assert isinstance(result.unwrap_err(), AuthenticationError)

    @pytest.mark.asyncio
    async def test_empty_header_value_returns_err(self) -> None:
        auth = APIKeyAuthenticator(APIKeyConfig(lookup={}))

        result = await auth.authenticate(
            {"headers": {"X-API-Key": ""}, "query_params": {}}
        )

        assert result.is_err()

    @pytest.mark.asyncio
    async def test_missing_context_keys_handled_gracefully(self) -> None:
        """request_context with no 'headers' or 'query_params' keys."""
        auth = APIKeyAuthenticator(APIKeyConfig(lookup={}))

        result = await auth.authenticate({})

        assert result.is_err()


# ---------------------------------------------------------------------------
# APIKeyAuthenticator — lookup variants
# ---------------------------------------------------------------------------


class TestAPIKeyAuthenticatorLookup:
    @pytest.mark.asyncio
    async def test_dict_lookup_invalid_key_returns_err(self) -> None:
        auth = APIKeyAuthenticator(APIKeyConfig(lookup={"valid_key": _make_user()}))

        result = await auth.authenticate(
            {"headers": {"X-API-Key": "invalid_key"}, "query_params": {}}
        )

        assert result.is_err()
        assert isinstance(result.unwrap_err(), AuthenticationError)

    @pytest.mark.asyncio
    async def test_async_callable_lookup(self) -> None:
        user = _make_user()

        async def lookup(key: str) -> User | None:
            return user if key == "valid" else None

        auth = APIKeyAuthenticator(APIKeyConfig(lookup=lookup))

        good = await auth.authenticate(
            {"headers": {"X-API-Key": "valid"}, "query_params": {}}
        )
        bad = await auth.authenticate(
            {"headers": {"X-API-Key": "wrong"}, "query_params": {}}
        )

        assert good.is_ok()
        assert good.unwrap() is user
        assert bad.is_err()

    @pytest.mark.asyncio
    async def test_sync_callable_lookup(self) -> None:
        user = _make_user()

        def lookup(key: str) -> User | None:
            return user if key == "sync_key" else None

        auth = APIKeyAuthenticator(APIKeyConfig(lookup=lookup))

        result = await auth.authenticate(
            {"headers": {"X-API-Key": "sync_key"}, "query_params": {}}
        )

        assert result.is_ok()
        assert result.unwrap() is user

    @pytest.mark.asyncio
    async def test_custom_header_name(self) -> None:
        user = _make_user()
        auth = APIKeyAuthenticator(
            APIKeyConfig(lookup={"tok": user}, header_name="X-Service-Token")
        )

        result = await auth.authenticate(
            {"headers": {"X-Service-Token": "tok"}, "query_params": {}}
        )

        assert result.is_ok()

    @pytest.mark.asyncio
    async def test_custom_query_param_name(self) -> None:
        user = _make_user()
        auth = APIKeyAuthenticator(
            APIKeyConfig(lookup={"tok": user}, query_param="token")
        )

        result = await auth.authenticate(
            {"headers": {}, "query_params": {"token": "tok"}}
        )

        assert result.is_ok()
