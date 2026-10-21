"""The deferred blacklist cache resolver is actually reachable.

``attach_cache_resolver`` documents a zero-argument callable, and
``AuthenticationProvider.boot`` supplies exactly that.  ``_effective_cache``
then called it with ``CacheBackendProtocol`` as a positional argument, so
every call raised ``TypeError``, logged ``blacklist_cache_resolve_failed``
and fell back to the per-process set — on every request, in every
application, with no durable revocation.  Found by qk-erp when it booted
``CacheModule`` and the warning did not go away.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import SecretStr

from quadkit.auth.authn.core import User
from quadkit.auth.authn.jwt import JWTTokenManager
from quadkit.auth.di.sub_providers.authentication_provider import (
    _resolve_default_cache_sync,
)
from quadkit.auth.exceptions import TokenBlacklistedError
from quadkit.result import Ok


class _Cache:
    def __init__(self) -> None:
        self.keys: dict[str, Any] = {}

    async def set(self, key: str, value: Any, ttl: int | None = None) -> Any:
        self.keys[key] = value
        return Ok(True)

    async def exists(self, key: str) -> Any:
        return Ok(key in self.keys)

    async def get(self, key: str) -> Any:
        return Ok(self.keys.get(key))

    async def delete(self, key: str) -> Any:
        return Ok(self.keys.pop(key, None) is not None)


def _manager() -> JWTTokenManager:
    return JWTTokenManager(
        current_key_id="default",
        keys={"default": SecretStr("secret_key_at_least_32_bytes_long_for_tests")},
        cache_service=None,
    )


@pytest.mark.asyncio
async def test_zero_arg_sync_resolver_is_called_without_arguments() -> None:
    cache = _Cache()
    calls: list[int] = []

    def resolver() -> Any:
        calls.append(1)
        return cache

    manager = _manager()
    manager.set_blacklist_resolver(resolver)
    user = User(user_id="u1", name="u", email="u@example.com")
    token = manager.create_access_token(user)

    assert (await manager.logout(token)).is_ok()
    assert calls == [1]
    assert any(key.startswith("jwt:blacklist:") for key in cache.keys), "revocation reached the cache"
    result = await manager.verify_token(token)
    assert result.is_err()
    assert isinstance(result.unwrap_err(), TokenBlacklistedError)


@pytest.mark.asyncio
async def test_resolver_returning_an_awaitable_is_awaited() -> None:
    cache = _Cache()

    class Container:
        async def resolve(self, protocol: Any) -> Any:
            return cache

    manager = _manager()
    manager.set_blacklist_resolver(lambda: _resolve_default_cache_sync(Container()))
    user = User(user_id="u1", name="u", email="u@example.com")
    token = manager.create_access_token(user)

    assert (await manager.logout(token)).is_ok()
    assert cache.keys, "the awaitable from container.resolve must be awaited, not discarded"


@pytest.mark.asyncio
async def test_legacy_one_argument_resolver_still_works() -> None:
    cache = _Cache()
    seen: list[Any] = []

    async def resolver(protocol: Any) -> Any:
        seen.append(protocol)
        return cache

    manager = _manager()
    manager.set_blacklist_resolver(resolver)
    user = User(user_id="u1", name="u", email="u@example.com")
    token = manager.create_access_token(user)

    assert (await manager.logout(token)).is_ok()
    assert cache.keys
    from quadkit.contracts.infra.cache import CacheBackendProtocol

    assert seen == [CacheBackendProtocol]


@pytest.mark.asyncio
async def test_resolver_that_yields_none_is_asked_again_later() -> None:
    cache = _Cache()
    state = {"ready": False, "calls": 0}

    def resolver() -> Any:
        state["calls"] += 1
        return cache if state["ready"] else None

    manager = _manager()
    manager.set_blacklist_resolver(resolver)
    user = User(user_id="u1", name="u", email="u@example.com")
    first = manager.create_access_token(user)
    assert (await manager.logout(first)).is_ok()
    assert not cache.keys, "no cache yet: fallback set"

    state["ready"] = True
    second = manager.create_access_token(user)
    assert (await manager.logout(second)).is_ok()
    assert cache.keys, "once the cache exists, revocation becomes durable"
    assert state["calls"] >= 2


class _ContractCache(_Cache):
    """A backend that honours the contract literally: ``set`` -> ``Ok(None)``."""

    async def set(self, key: str, value: Any, ttl: int | None = None) -> Any:
        self.keys[key] = value
        return Ok(None)


@pytest.mark.asyncio
async def test_ok_none_from_set_is_a_successful_revocation() -> None:
    cache = _ContractCache()
    manager = _manager()
    manager.set_blacklist_resolver(lambda: cache)
    user = User(user_id="u1", name="u", email="u@example.com")
    token = manager.create_access_token(user)

    result = await manager.logout(token)
    assert result.is_ok(), "Ok(None) is the contract's success value, not a failure"
    assert cache.keys
    verify = await manager.verify_token(token)
    assert verify.is_err()
    assert isinstance(verify.unwrap_err(), TokenBlacklistedError)


@pytest.mark.asyncio
async def test_ok_none_from_set_is_a_successful_revoke_all() -> None:
    cache = _ContractCache()
    manager = _manager()
    manager.set_blacklist_resolver(lambda: cache)
    user = User(user_id="u1", name="u", email="u@example.com")
    token = manager.create_access_token(user)

    result = await manager.logout_all_user_tokens("u1")
    assert result.is_ok()
    verify = await manager.verify_token(token)
    assert verify.is_err()
