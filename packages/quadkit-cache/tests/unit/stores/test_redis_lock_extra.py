"""Focused tests for the Redis lock store."""

from __future__ import annotations

from typing import Any

import pytest

from quadkit.cache.stores.redis_lock import RedisLockStore
from quadkit.contracts.exceptions.components import (
    LockAcquisitionError,
    LockNotHeldError,
    LockOwnershipError,
)
from quadkit.contracts.core.health import HealthStatus


class _FakeClient:
    def __init__(self) -> None:
        self.set_result: Any = True
        self.eval_result: Any = 1
        self.exists_result: Any = 0
        self.ping_result: Any | Exception = True
        self.set_calls: list[tuple] = []
        self.eval_calls: list[tuple] = []
        self.pinged = 0

    async def set(self, key: str, value: str, px: int, nx: bool) -> Any:
        self.set_calls.append((key, value, px, nx))
        return self.set_result

    async def eval(self, script: str, numkeys: int, *args: Any) -> Any:
        self.eval_calls.append((script, numkeys, args))
        return self.eval_result

    async def exists(self, key: str) -> Any:
        return self.exists_result

    async def ping(self) -> Any:
        self.pinged += 1
        if isinstance(self.ping_result, Exception):
            raise self.ping_result
        return self.ping_result


def test_module_binds_the_async_redis_client() -> None:
    # Regression: the store awaits every client call, so it must bind
    # redis.asyncio — top-level redis.from_url returns a *synchronous*
    # client whose results cannot be awaited.
    import quadkit.cache.stores.redis_lock as module

    if not module.HAS_REDIS:
        pytest.skip("redis driver not installed")
    import redis.asyncio

    assert module.redis is redis.asyncio


@pytest.mark.asyncio
async def test_acquire_requires_owner() -> None:
    store = RedisLockStore(client=_FakeClient())
    with pytest.raises(ValueError, match="owner parameter is required"):
        await store.acquire("res")


@pytest.mark.asyncio
async def test_acquire_success_with_prefix() -> None:
    client = _FakeClient()
    store = RedisLockStore(prefix="tenant1:", client=client)
    lock_id = await store.acquire("res", ttl=30, owner="svc")
    assert lock_id is not None
    assert lock_id.startswith("svc:")
    assert client.set_calls[0][0] == "tenant1:lock:res"
    assert client.set_calls[0][2] == 30000
    assert client.set_calls[0][3] is True


@pytest.mark.asyncio
async def test_acquire_failure_returns_none() -> None:
    client = _FakeClient()
    client.set_result = None
    store = RedisLockStore(client=client)
    assert await store.acquire("res", owner="svc") is None


@pytest.mark.asyncio
async def test_release_success() -> None:
    client = _FakeClient()
    client.eval_result = 1
    store = RedisLockStore(client=client)
    assert await store.release("res", "svc:abc") is None
    assert client.eval_calls[0][2][0] == "lock:res"


@pytest.mark.asyncio
async def test_release_not_held_raises() -> None:
    client = _FakeClient()
    client.eval_result = -1
    store = RedisLockStore(client=client)
    with pytest.raises(LockNotHeldError):
        await store.release("res", "svc:abc")


@pytest.mark.asyncio
async def test_release_ownership_mismatch_raises() -> None:
    # Ownership mismatch is a distinct error type: callers must be able to
    # tell "lock expired/absent" (LockNotHeldError) from "someone else
    # holds it" (LockOwnershipError).
    client = _FakeClient()
    client.eval_result = 0
    store = RedisLockStore(client=client)
    with pytest.raises(LockOwnershipError) as exc_info:
        await store.release("res", "other:abc")
    assert not isinstance(exc_info.value, LockNotHeldError)
    assert exc_info.value.resource == "res"


@pytest.mark.asyncio
async def test_extend_success() -> None:
    client = _FakeClient()
    client.eval_result = 1
    store = RedisLockStore(client=client)
    assert await store.extend("res", "svc:abc", ttl=60) is None
    script, numkeys, args = client.eval_calls[0]
    assert numkeys == 1
    assert args[1] == "svc:abc"
    assert args[2] == 60000


@pytest.mark.asyncio
async def test_extend_not_held_raises() -> None:
    client = _FakeClient()
    client.eval_result = -1
    store = RedisLockStore(client=client)
    with pytest.raises(LockNotHeldError):
        await store.extend("res", "svc:abc", ttl=60)


@pytest.mark.asyncio
async def test_extend_ownership_mismatch_raises() -> None:
    client = _FakeClient()
    client.eval_result = 0
    store = RedisLockStore(client=client)
    with pytest.raises(LockOwnershipError) as exc_info:
        await store.extend("res", "other:abc", ttl=60)
    assert not isinstance(exc_info.value, LockNotHeldError)


@pytest.mark.asyncio
async def test_is_locked_true() -> None:
    client = _FakeClient()
    client.exists_result = 1
    store = RedisLockStore(prefix="p:", client=client)
    assert await store.is_locked("res") is True


@pytest.mark.asyncio
async def test_is_locked_false() -> None:
    client = _FakeClient()
    client.exists_result = 0
    store = RedisLockStore(client=client)
    assert await store.is_locked("res") is False


@pytest.mark.asyncio
async def test_locked_context_manager_success() -> None:
    client = _FakeClient()
    client.eval_result = 1
    store = RedisLockStore(client=client)
    async with store.locked("res", owner="svc") as lock_id:
        assert lock_id is not None


@pytest.mark.asyncio
async def test_locked_context_manager_acquire_failure_raises() -> None:
    client = _FakeClient()
    client.set_result = None
    store = RedisLockStore(client=client)
    with pytest.raises(LockAcquisitionError):
        async with store.locked("res", owner="svc"):
            pytest.fail("should not enter")


@pytest.mark.asyncio
async def test_locked_context_manager_tolerates_stale_release() -> None:
    # The lock expired while the body was running: release finds nothing.
    # Acquire uses SET (fake returns True); the only eval call is the
    # release, which observes the lock gone (-1). The expected stale case
    # must not propagate out of the context manager.
    client = _FakeClient()
    client.eval_result = -1
    store = RedisLockStore(client=client)

    async with store.locked("res", owner="svc"):
        pass

    assert len(client.eval_calls) == 1


async def test_locked_context_manager_tolerates_transient_release_failure() -> None:
    # A transient connectivity failure during release must not mask the
    # body's outcome — the lock expires by TTL.
    client = _FakeClient()

    real_eval = client.eval

    async def failing_eval(script: str, numkeys: int, *args: Any) -> Any:
        client.eval_calls.append((script, numkeys, args))
        raise ConnectionError("redis went away")

    client.eval = failing_eval  # type: ignore[method-assign]
    store = RedisLockStore(client=client)

    async with store.locked("res", owner="svc"):
        pass  # must not raise


async def test_locked_context_manager_generates_default_owner() -> None:
    # Omitting owner must not produce "None:<uuid>" lock ids.
    client = _FakeClient()
    store = RedisLockStore(client=client)
    async with store.locked("res"):
        pass
    (_key, lock_id, _px, _nx), = client.set_calls
    assert not lock_id.startswith("None:")
    assert ":" in lock_id


@pytest.mark.asyncio
async def test_health_check_healthy() -> None:
    store = RedisLockStore(url="redis://x", client=_FakeClient())
    result = await store.health_check()
    assert result.status is HealthStatus.HEALTHY
    assert result.component == "lock_store"


@pytest.mark.asyncio
async def test_health_check_unhealthy() -> None:
    client = _FakeClient()
    client.ping_result = ConnectionError("down")
    store = RedisLockStore(url="redis://x", client=client)
    result = await store.health_check()
    assert result.status is HealthStatus.UNHEALTHY
    assert "down" in result.error


@pytest.mark.asyncio
async def test_lazy_client_requires_redis_driver(monkeypatch: pytest.MonkeyPatch) -> None:
    import quadkit.cache.stores.redis_lock as module

    monkeypatch.setattr(module, "HAS_REDIS", False)
    store = RedisLockStore()
    with pytest.raises(ImportError, match="Redis driver is required"):
        await store._get_client()


class TestRedisLockStoreClose:
    """close() releases the Redis client pool."""

    class _RecordingClient:
        def __init__(self) -> None:
            self.aclose_calls = 0

        async def aclose(self) -> None:
            self.aclose_calls += 1

    @pytest.mark.asyncio
    async def test_close_closes_injected_client_and_clears_reference(self) -> None:
        client = self._RecordingClient()
        store = RedisLockStore(url="redis://x", client=client)
        await store.close()
        assert client.aclose_calls == 1
        assert store._client is None

    @pytest.mark.asyncio
    async def test_close_without_client_is_noop(self) -> None:
        store = RedisLockStore(url="redis://x")
        await store.close()
        assert store._client is None
