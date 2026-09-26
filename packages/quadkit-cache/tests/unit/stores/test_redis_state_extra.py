"""Focused tests for the Redis state store."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest

from quadkit.cache.stores.redis_state import RedisDriver, RedisStateStore
from quadkit.contracts.core.health import HealthStatus


class _FakeClient:
    def __init__(self) -> None:
        self.get_result: Any = None
        self.mget_result: Any = []
        self.info_result: dict[str, Any] = {}
        self.ping_result: Any | Exception = True
        self.set_calls: list[tuple] = []
        self.delete_calls: list[str] = []

    async def get(self, key: str) -> Any:
        return self.get_result

    async def mget(self, keys: list[str]) -> Any:
        return self.mget_result

    async def set(self, key: str, value: str, ex: int | None = None) -> Any:
        self.set_calls.append((key, value, ex))
        return True

    async def delete(self, key: str) -> Any:
        self.delete_calls.append(key)
        return 1

    async def ping(self) -> Any:
        if isinstance(self.ping_result, Exception):
            raise self.ping_result
        return self.ping_result

    async def info(self) -> dict[str, Any]:
        return self.info_result


@pytest.fixture
def client() -> _FakeClient:
    return _FakeClient()


class TestGetSetDelete:
    @pytest.mark.asyncio
    async def test_get_returns_deserialized(self, client: _FakeClient) -> None:
        client.get_result = '{"a": 1}'
        store = RedisStateStore(client=client)
        assert await store.get("k") == {"a": 1}

    @pytest.mark.asyncio
    async def test_get_missing_returns_none(self, client: _FakeClient) -> None:
        store = RedisStateStore(prefix="p:", client=client)
        assert await store.get("k") is None

    @pytest.mark.asyncio
    async def test_set_plain_value(self, client: _FakeClient) -> None:
        store = RedisStateStore(client=client)
        await store.set("k", {"a": 1}, ttl=10)
        assert client.set_calls[0][1] == b'{"a":1}'
        assert client.set_calls[0][2] == 10

    @pytest.mark.asyncio
    async def test_set_value_with_json_method(self, client: _FakeClient) -> None:
        class Jsonish:
            def json(self) -> str:
                return '{"x": 2}'

        store = RedisStateStore(client=client)
        await store.set("k", Jsonish())
        assert client.set_calls[0][1] == '{"x": 2}'

    @pytest.mark.asyncio
    async def test_set_domain_model_dumps_dict(self, client: _FakeClient) -> None:
        from quadkit.domain import DomainModel
        from dataclasses import dataclass

        @dataclass
        class Thing(DomainModel):
            name: str = "t"

        store = RedisStateStore(client=client)
        await store.set("k", Thing())
        value = client.set_calls[0][1]
        assert '"name"' in value.decode() and '"t"' in value.decode()

    @pytest.mark.asyncio
    async def test_delete_returns_true(self, client: _FakeClient) -> None:
        store = RedisStateStore(prefix="pre:", client=client)
        assert await store.delete("k") is True
        assert client.delete_calls == ["pre:k"]


class TestGetBulk:
    @pytest.mark.asyncio
    async def test_get_bulk_maps_values(self, client: _FakeClient) -> None:
        client.mget_result = ['{"a": 1}', None, '{"c": 3}']
        store = RedisStateStore(prefix="p:", client=client)
        result = await store.get_bulk(["a", "b", "c"])
        assert result == {"a": {"a": 1}, "c": {"c": 3}}


class TestJsonEncoder:
    def test_datetime_isoformat(self) -> None:
        driver = RedisDriver()
        value = datetime(2026, 1, 1, tzinfo=UTC)
        assert driver._json_encoder(value) == "2026-01-01T00:00:00+00:00"

    def test_uuid_str(self) -> None:
        assert RedisDriver()._json_encoder(UUID(int=1)) == "00000000-0000-0000-0000-000000000001"

    def test_object_dict(self) -> None:
        class Obj:
            def __init__(self) -> None:
                self.a = 1

        assert RedisDriver()._json_encoder(Obj()) == {"a": 1}

    def test_fallback_str(self) -> None:
        assert RedisDriver()._json_encoder(3) == "3"


class TestHealth:
    @pytest.mark.asyncio
    async def test_health_check_healthy(self, client: _FakeClient) -> None:
        client.info_result = {"connected_clients": 2}
        store = RedisStateStore(url="redis://x", client=client)
        result = await store.health_check()
        assert result.status is HealthStatus.HEALTHY
        assert result.details["connected_clients"] == 2
        assert result.details["used_memory"] == "unknown"

    @pytest.mark.asyncio
    async def test_health_check_unhealthy(self, client: _FakeClient) -> None:
        client.ping_result = ConnectionError("down")
        store = RedisStateStore(url="redis://x", client=client)
        result = await store.health_check()
        assert result.status is HealthStatus.UNHEALTHY
        assert "down" in result.error


@pytest.mark.asyncio
async def test_lazy_client_missing_driver_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import quadkit.cache.stores.redis_state as module

    monkeypatch.setattr(module, "HAS_REDIS", False)
    store = RedisStateStore()
    with pytest.raises(ImportError, match="Redis driver is required"):
        await store._get_client()


class TestRedisStateStoreClose:
    """close() releases the Redis client pool."""

    class _RecordingClient:
        def __init__(self) -> None:
            self.aclose_calls = 0

        async def aclose(self) -> None:
            self.aclose_calls += 1

    @pytest.mark.asyncio
    async def test_close_closes_lazy_client_and_clears_reference(self) -> None:
        client = self._RecordingClient()
        store = RedisStateStore(url="redis://x", client=client)
        await store.close()
        assert client.aclose_calls == 1
        assert store._client is None

    @pytest.mark.asyncio
    async def test_close_without_client_is_noop(self) -> None:
        store = RedisStateStore(url="redis://x")
        await store.close()
        assert store._client is None

    @pytest.mark.asyncio
    async def test_close_with_sync_close_fallback(self) -> None:
        class _SyncCloseClient:
            def __init__(self) -> None:
                self.close_calls = 0

            def close(self) -> None:
                self.close_calls += 1

        client = _SyncCloseClient()
        store = RedisStateStore(url="redis://x", client=client)
        await store.close()
        assert client.close_calls == 1
        assert store._client is None
