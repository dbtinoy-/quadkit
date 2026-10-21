"""Guards for the ``StateStoreProtocol`` implementations.

``StateStoreProtocol`` is a plain ``typing.Protocol`` whose members carry
docstring-only bodies. Subclassing it therefore does **not** make Python enforce
anything at runtime: an implementation that forgets a method silently inherits
the stub, and calling that method returns ``None`` instead of raising. Only
mypy notices.

That is exactly what happened — ``MemoryStateStore`` shipped without
``expire``/``ttl``/``get_many``/``set_many`` and ``RedisStateStore`` without
``exists`` on top of those four, so three call sites carried
``# type: ignore[abstract]`` to silence the resulting
"cannot instantiate abstract class" errors.

The first test is the regression guard: it fails if any implementation starts
inheriting a protocol stub again. The rest pin the behaviour the protocol's
docstrings promise.
"""

from __future__ import annotations

import inspect
from typing import Any

import pytest

from quadkit.cache.backends.memory_state import MemoryStateStore
from quadkit.cache.stores.redis_state import RedisStateStore
from quadkit.contracts.infra.state import StateStoreProtocol


def _protocol_methods() -> list[str]:
    """Names declared directly on the protocol (not inherited dunders)."""
    return sorted(
        name
        for name, member in vars(StateStoreProtocol).items()
        if not name.startswith("_") and inspect.isfunction(member)
    )


def _inherited_stub(cls: type, method: str) -> bool:
    """True when *cls* resolves *method* to the protocol's own stub body."""
    fn = getattr(cls, method, None)
    if fn is None:
        return True
    return getattr(fn, "__qualname__", "").startswith("StateStoreProtocol")


class _FakeClient:
    """Minimal async stand-in for ``redis.asyncio.Redis``."""

    def __init__(self) -> None:
        self.exists_result: Any = 1
        self.expire_result: Any = True
        self.ttl_result: Any = 42
        self.mget_result: Any = []
        self.set_calls: list[tuple] = []
        self.expire_calls: list[tuple] = []

    async def exists(self, key: str) -> Any:
        return self.exists_result

    async def expire(self, key: str, seconds: int) -> Any:
        self.expire_calls.append((key, seconds))
        return self.expire_result

    async def ttl(self, key: str) -> Any:
        return self.ttl_result

    async def mget(self, keys: list[str]) -> Any:
        return self.mget_result

    async def set(self, key: str, value: str, ex: int | None = None) -> Any:
        self.set_calls.append((key, value, ex))
        return True


@pytest.mark.parametrize("cls", [MemoryStateStore, RedisStateStore])
def test_every_protocol_method_is_really_implemented(cls: type) -> None:
    """No implementation may resolve a method to the protocol's empty stub."""
    methods = _protocol_methods()
    assert methods, "StateStoreProtocol declared nothing — the guard is vacuous"
    inherited = [m for m in methods if _inherited_stub(cls, m)]
    assert inherited == [], f"{cls.__name__} inherits protocol stubs for {inherited}"


class TestMemoryStateStoreContract:
    @pytest.mark.asyncio
    async def test_ttl_reports_no_expiry(self) -> None:
        store = MemoryStateStore()
        await store.set("k", "v")
        assert await store.ttl("k") == -1

    @pytest.mark.asyncio
    async def test_ttl_reports_absent_key(self) -> None:
        store = MemoryStateStore()
        assert await store.ttl("nope") == -2

    @pytest.mark.asyncio
    async def test_ttl_reports_remaining_seconds(self) -> None:
        store = MemoryStateStore()
        await store.set("k", "v", ttl=60)
        remaining = await store.ttl("k")
        assert 0 < remaining <= 60

    @pytest.mark.asyncio
    async def test_expire_sets_a_new_deadline(self) -> None:
        store = MemoryStateStore()
        await store.set("k", "v")
        assert await store.expire("k", 30) is True
        remaining = await store.ttl("k")
        assert 0 < remaining <= 30

    @pytest.mark.asyncio
    async def test_expire_on_missing_key_returns_false(self) -> None:
        store = MemoryStateStore()
        assert await store.expire("nope", 30) is False

    @pytest.mark.asyncio
    async def test_expire_on_expired_key_returns_false_and_reaps(self) -> None:
        store = MemoryStateStore()
        await store.set("k", "v", ttl=-1)  # already in the past
        assert await store.expire("k", 30) is False
        assert await store.get("k") is None

    @pytest.mark.asyncio
    async def test_get_many_omits_absent_keys(self) -> None:
        store = MemoryStateStore()
        await store.set("a", 1)
        await store.set("b", {"nested": True})
        assert await store.get_many(["a", "b", "missing"]) == {
            "a": 1,
            "b": {"nested": True},
        }

    @pytest.mark.asyncio
    async def test_set_many_applies_ttl_to_every_entry(self) -> None:
        store = MemoryStateStore()
        await store.set_many({"a": 1, "b": 2}, ttl=120)
        assert await store.get_many(["a", "b"]) == {"a": 1, "b": 2}
        for key in ("a", "b"):
            remaining = await store.ttl(key)
            assert 0 < remaining <= 120


class TestRedisStateStoreContract:
    @pytest.mark.asyncio
    async def test_exists_maps_truthiness(self) -> None:
        client = _FakeClient()
        store = RedisStateStore(client=client)
        assert await store.exists("k") is True
        client.exists_result = 0
        assert await store.exists("k") is False

    @pytest.mark.asyncio
    async def test_expire_forwards_key_and_seconds(self) -> None:
        client = _FakeClient()
        store = RedisStateStore(prefix="p:", client=client)
        assert await store.expire("k", 90) is True
        assert client.expire_calls == [("p:k", 90)]

    @pytest.mark.asyncio
    async def test_expire_returns_false_when_key_missing(self) -> None:
        client = _FakeClient()
        client.expire_result = False
        store = RedisStateStore(client=client)
        assert await store.expire("k", 90) is False

    @pytest.mark.asyncio
    async def test_ttl_passes_through_redis_sentinels(self) -> None:
        client = _FakeClient()
        store = RedisStateStore(client=client)
        assert await store.ttl("k") == 42
        client.ttl_result = -1
        assert await store.ttl("k") == -1
        client.ttl_result = -2
        assert await store.ttl("k") == -2

    @pytest.mark.asyncio
    async def test_get_many_returns_found_keys_only(self) -> None:
        client = _FakeClient()
        client.mget_result = ['{"a":1}', None]
        store = RedisStateStore(client=client)
        assert await store.get_many(["a", "b"]) == {"a": {"a": 1}}

    @pytest.mark.asyncio
    async def test_set_many_writes_each_entry_with_ttl(self) -> None:
        client = _FakeClient()
        store = RedisStateStore(client=client)
        await store.set_many({"a": 1, "b": {"n": 2}}, ttl=15)
        # Each entry is serialised on its own: `set_many` forwards the value,
        # not a wrapper dict.
        assert list(client.set_calls) == [
            ("a", b"1", 15),
            ("b", b'{"n":2}', 15),
        ]
