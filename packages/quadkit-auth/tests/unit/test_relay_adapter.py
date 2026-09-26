"""Adapter tests for the relay gateway API-key verifier.

``RelayApiKeyVerifier`` binds quadkit-auth's ``APIKeyManager`` behind
the framework's ``RelayAuthVerifierProtocol`` so the relay gateway can
enforce API-key auth without importing quadkit-auth.  The tests use a
real manager with a fake repository (same pattern as test_enterprise_features)
and duck-typed request doubles.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from quadkit.auth.authn.apikeys import APIKeyManager
from quadkit.auth.authn.relay import RelayApiKeyVerifier
from quadkit.auth.authn.security import PasswordHasher
from quadkit.contracts.ai.relay import RelayAuthError, RelayAuthIdentity
from quadkit.contracts.core.result import Err, Ok, Result

USER_ID = "u1"
KEY_ID = "key-1"


def make_manager() -> tuple[APIKeyManager, Any]:
    """Build a real manager backed by a fake repo with one seeded row."""
    repo = SimpleNamespace(
        insert=async_return(KEY_ID),
        find_by_prefix=async_return([]),
        find_by_user=async_return([]),
        update_last_used=async_return(None),
        revoke=async_return(True),
    )
    return APIKeyManager(repo=repo), repo


async def seed_key(repo: Any, raw_key: str) -> dict[str, Any]:
    """Seed the fake repo with a hash row for *raw_key*."""
    row = {
        "id": KEY_ID,
        "name": "test",
        "key_hash": await PasswordHasher().hash(raw_key),
        "prefix": raw_key[:8],
        "user_id": USER_ID,
        "scopes": [],
        "expires_at": None,
        "created_at": None,
        "updated_at": None,
    }
    repo.find_by_prefix = async_return([row])
    return row


def async_return(value: Any) -> Any:
    """Return an async callable yielding *value*."""

    async def _call(*args: Any, **kwargs: Any) -> Any:
        return value

    return _call


def make_request(
    *,
    path: str = "/v1/chat/completions",
    headers: dict[str, str] | None = None,
    query: dict[str, str] | None = None,
) -> Any:
    """Build a duck-typed request double with the header/query surface."""
    return SimpleNamespace(
        path=path,
        headers=headers if headers is not None else {},
        query_params=query if query is not None else {},
        client=SimpleNamespace(host="1.2.3.4"),
    )


class TestRelayApiKeyVerifier:
    async def test_valid_bearer_key_ok(self) -> None:
        manager, repo = make_manager()
        await seed_key(repo, "sk_live_abc123")
        verifier = RelayApiKeyVerifier(manager)
        result: Result[RelayAuthIdentity, RelayAuthError] = await verifier.authenticate(
            make_request(headers={"Authorization": "Bearer sk_live_abc123"})
        )
        assert isinstance(result, Ok)
        assert result.unwrap().user_id == USER_ID
        assert result.unwrap().token_id == KEY_ID

    async def test_lowercase_bearer_ok(self) -> None:
        manager, repo = make_manager()
        await seed_key(repo, "sk_live_abc123")
        verifier = RelayApiKeyVerifier(manager)
        result = await verifier.authenticate(
            make_request(headers={"Authorization": "bearer sk_live_abc123"})
        )
        assert isinstance(result, Ok)

    async def test_invalid_key_err(self) -> None:
        manager, repo = make_manager()
        await seed_key(repo, "sk_live_abc123")
        verifier = RelayApiKeyVerifier(manager)
        result = await verifier.authenticate(
            make_request(headers={"Authorization": "Bearer sk_live_wrong"})
        )
        assert isinstance(result, Err)
        assert result.unwrap_err().code == "AUTH_TOKEN_INVALID"

    async def test_disabled_user_err(self) -> None:
        manager, repo = make_manager()
        await seed_key(repo, "sk_live_abc123")

        async def checker(user_id: str) -> bool:
            return False

        verifier = RelayApiKeyVerifier(manager, user_status_checker=checker)
        result = await verifier.authenticate(
            make_request(headers={"Authorization": "Bearer sk_live_abc123"})
        )
        assert isinstance(result, Err)
        assert result.unwrap_err().code == "AUTH_USER_DISABLED"

    async def test_active_user_ok(self) -> None:
        manager, repo = make_manager()
        await seed_key(repo, "sk_live_abc123")

        async def checker(user_id: str) -> bool:
            return True

        verifier = RelayApiKeyVerifier(manager, user_status_checker=checker)
        result = await verifier.authenticate(
            make_request(headers={"Authorization": "Bearer sk_live_abc123"})
        )
        assert isinstance(result, Ok)

    async def test_x_api_key_fallback(self) -> None:
        manager, repo = make_manager()
        await seed_key(repo, "sk_live_abc123")
        verifier = RelayApiKeyVerifier(manager)
        result = await verifier.authenticate(
            make_request(
                path="/v1/messages",
                headers={"x-api-key": "sk_live_abc123"},
            )
        )
        assert isinstance(result, Ok)

    async def test_x_goog_api_key_fallback(self) -> None:
        manager, repo = make_manager()
        await seed_key(repo, "sk_live_abc123")
        verifier = RelayApiKeyVerifier(manager)
        result = await verifier.authenticate(
            make_request(
                path="/v1beta/models/gemini:generateContent",
                headers={"x-goog-api-key": "sk_live_abc123"},
            )
        )
        assert isinstance(result, Ok)

    async def test_query_key_fallback(self) -> None:
        manager, repo = make_manager()
        await seed_key(repo, "sk_live_abc123")
        verifier = RelayApiKeyVerifier(manager)
        result = await verifier.authenticate(
            make_request(
                path="/v1beta/models/gemini:generateContent",
                query={"key": "sk_live_abc123"},
            )
        )
        assert isinstance(result, Ok)

    async def test_missing_credentials_err(self) -> None:
        manager, repo = make_manager()
        await seed_key(repo, "sk_live_abc123")
        verifier = RelayApiKeyVerifier(manager)
        result = await verifier.authenticate(make_request())
        assert isinstance(result, Err)
        assert result.unwrap_err().code == "AUTH_TOKEN_INVALID"

    async def test_query_wins_over_x_goog(self) -> None:
        manager, repo = make_manager()
        await seed_key(repo, "sk_live_abc123")
        verifier = RelayApiKeyVerifier(manager)
        result = await verifier.authenticate(
            make_request(
                path="/v1beta/models/gemini:generateContent",
                headers={"x-goog-api-key": "sk_live_bad"},
                query={"key": "sk_live_abc123"},
            )
        )
        assert isinstance(result, Ok)
