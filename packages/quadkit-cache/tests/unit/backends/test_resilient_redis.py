"""Focused tests for the resilient Redis cache backend decorator."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

import pytest

from quadkit.cache.backends.redis.resilient import ResilientRedisCacheBackend
from quadkit.contracts.infra.cache.exceptions import CacheError
from quadkit.result import Err


class _OkBreaker:
    async def call(self, fn: Callable[..., Awaitable[Any]], *args: Any, **kwargs: Any) -> Any:
        return await fn(*args, **kwargs)


class _RaisingBreaker:
    def __init__(self, error: Exception) -> None:
        self._error = error

    async def call(self, fn: Callable[..., Awaitable[Any]], *args: Any, **kwargs: Any) -> Any:
        raise self._error


class _Inner:
    async def get(self, key: str) -> Any:
        return f"v:{key}"

    async def set(self, key: str, value: Any, ttl: int | None = None) -> Any:
        return "OK"

    async def delete(self, key: str) -> Any:
        return True

    async def exists(self, key: str) -> Any:
        return True

    async def clear(self) -> Any:
        return True

    async def get_many(self, keys: list[str]) -> Any:
        return {k: f"v:{k}" for k in keys}

    async def set_many(self, items: dict[str, Any], ttl: int | None = None) -> Any:
        return "OK"

    async def delete_many(self, keys: list[str]) -> Any:
        return True

    async def delete_pattern(self, pattern: str) -> Any:
        return ["a", "b"]

    async def health_check(self, timeout: float = 5.0) -> Any:
        from quadkit.contracts.core.health import HealthCheckResult, HealthStatus

        return HealthCheckResult(
            component="inner", status=HealthStatus.HEALTHY, checked_at=None
        )


@pytest.fixture
def inner() -> _Inner:
    return _Inner()


@pytest.mark.asyncio
async def test_get_success(inner: _Inner) -> None:
    backend = ResilientRedisCacheBackend(inner=inner, breaker=_OkBreaker())
    assert await backend.get("k") == "v:k"


@pytest.mark.asyncio
async def test_get_circuit_open_returns_err(inner: _Inner) -> None:
    backend = ResilientRedisCacheBackend(
        inner=inner, breaker=_RaisingBreaker(ConnectionError("down"))
    )
    result = await backend.get("k")
    assert isinstance(result, Err)
    assert isinstance(result.unwrap_err(), CacheError)


@pytest.mark.asyncio
async def test_set_success(inner: _Inner) -> None:
    backend = ResilientRedisCacheBackend(inner=inner, breaker=_OkBreaker())
    assert await backend.set("k", "v", ttl=10) == "OK"


@pytest.mark.asyncio
async def test_set_circuit_open_returns_err(inner: _Inner) -> None:
    backend = ResilientRedisCacheBackend(
        inner=inner, breaker=_RaisingBreaker(ConnectionError("down"))
    )
    result = await backend.set("k", "v")
    assert isinstance(result, Err)
    assert isinstance(result.unwrap_err(), CacheError)


@pytest.mark.asyncio
async def test_delete_success(inner: _Inner) -> None:
    backend = ResilientRedisCacheBackend(inner=inner, breaker=_OkBreaker())
    assert await backend.delete("k") is True


@pytest.mark.asyncio
async def test_delete_circuit_open_returns_err(inner: _Inner) -> None:
    backend = ResilientRedisCacheBackend(
        inner=inner, breaker=_RaisingBreaker(ConnectionError("down"))
    )
    result = await backend.delete("k")
    assert isinstance(result, Err)
    assert isinstance(result.unwrap_err(), CacheError)


@pytest.mark.asyncio
async def test_exists_success(inner: _Inner) -> None:
    backend = ResilientRedisCacheBackend(inner=inner, breaker=_OkBreaker())
    assert await backend.exists("k") is True


@pytest.mark.asyncio
async def test_exists_circuit_open_returns_err(inner: _Inner) -> None:
    backend = ResilientRedisCacheBackend(
        inner=inner, breaker=_RaisingBreaker(ConnectionError("down"))
    )
    result = await backend.exists("k")
    assert isinstance(result, Err)
    assert isinstance(result.unwrap_err(), CacheError)


@pytest.mark.asyncio
async def test_clear_success(inner: _Inner) -> None:
    backend = ResilientRedisCacheBackend(inner=inner, breaker=_OkBreaker())
    assert await backend.clear() is True


@pytest.mark.asyncio
async def test_clear_circuit_open_returns_err(inner: _Inner) -> None:
    backend = ResilientRedisCacheBackend(
        inner=inner, breaker=_RaisingBreaker(ConnectionError("down"))
    )
    result = await backend.clear()
    assert isinstance(result, Err)
    assert isinstance(result.unwrap_err(), CacheError)


@pytest.mark.asyncio
async def test_get_many_success(inner: _Inner) -> None:
    backend = ResilientRedisCacheBackend(inner=inner, breaker=_OkBreaker())
    assert await backend.get_many(["a", "b"]) == {"a": "v:a", "b": "v:b"}


@pytest.mark.asyncio
async def test_get_many_circuit_open_returns_err(inner: _Inner) -> None:
    backend = ResilientRedisCacheBackend(
        inner=inner, breaker=_RaisingBreaker(ConnectionError("down"))
    )
    result = await backend.get_many(["a"])
    assert isinstance(result, Err)
    assert isinstance(result.unwrap_err(), CacheError)


@pytest.mark.asyncio
async def test_set_many_success(inner: _Inner) -> None:
    backend = ResilientRedisCacheBackend(inner=inner, breaker=_OkBreaker())
    assert await backend.set_many({"a": 1}, ttl=5) == "OK"


@pytest.mark.asyncio
async def test_set_many_circuit_open_returns_err(inner: _Inner) -> None:
    backend = ResilientRedisCacheBackend(
        inner=inner, breaker=_RaisingBreaker(ConnectionError("down"))
    )
    result = await backend.set_many({"a": 1})
    assert isinstance(result, Err)
    assert isinstance(result.unwrap_err(), CacheError)


@pytest.mark.asyncio
async def test_delete_many_success(inner: _Inner) -> None:
    backend = ResilientRedisCacheBackend(inner=inner, breaker=_OkBreaker())
    assert await backend.delete_many(["a"]) is True


@pytest.mark.asyncio
async def test_delete_many_circuit_open_returns_err(inner: _Inner) -> None:
    backend = ResilientRedisCacheBackend(
        inner=inner, breaker=_RaisingBreaker(ConnectionError("down"))
    )
    result = await backend.delete_many(["a"])
    assert isinstance(result, Err)
    assert isinstance(result.unwrap_err(), CacheError)


@pytest.mark.asyncio
async def test_delete_pattern_success(inner: _Inner) -> None:
    backend = ResilientRedisCacheBackend(inner=inner, breaker=_OkBreaker())
    assert await backend.delete_pattern("k:*") == ["a", "b"]


@pytest.mark.asyncio
async def test_delete_pattern_circuit_open_returns_err(inner: _Inner) -> None:
    backend = ResilientRedisCacheBackend(
        inner=inner, breaker=_RaisingBreaker(ConnectionError("down"))
    )
    result = await backend.delete_pattern("k:*")
    assert isinstance(result, Err)
    assert isinstance(result.unwrap_err(), CacheError)


@pytest.mark.asyncio
async def test_health_check_success(inner: _Inner) -> None:
    backend = ResilientRedisCacheBackend(inner=inner, breaker=_OkBreaker())
    result = await backend.health_check()
    assert result.component == "inner"


@pytest.mark.asyncio
async def test_health_check_circuit_open_unhealthy(inner: _Inner) -> None:
    from quadkit.contracts.core.health import HealthStatus

    backend = ResilientRedisCacheBackend(
        inner=inner, breaker=_RaisingBreaker(ConnectionError("down"))
    )
    result = await backend.health_check()
    assert result.status is HealthStatus.UNHEALTHY
    assert "down" in result.error