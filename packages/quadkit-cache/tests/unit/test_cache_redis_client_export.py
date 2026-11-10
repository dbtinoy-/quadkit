"""Unit tests for CacheModule / CacheProvider RedisClientProtocol export."""

from __future__ import annotations

from quadkit.cache.di.provider import CacheProvider
from quadkit.cache.module import CacheModule
from quadkit.contracts.infra.redis import RedisClientProtocol


class _FakeRedisBackend:
    def __init__(self, client: object) -> None:
        self._raw = client

    def get_underlying_client(self) -> object:
        return self._raw


class _FakeCircuitBreakerWrapper:
    def __init__(self, inner: object) -> None:
        self._backend = inner


def test_cache_module_exports_redis_client_protocol() -> None:
    """CacheModule.configure and CacheModule.stub export RedisClientProtocol."""
    assert RedisClientProtocol in CacheModule.configure().exports
    assert RedisClientProtocol in CacheModule.stub().exports


def test_get_redis_client_unwraps_decorator_and_handles_memory() -> None:
    """CacheProvider.get_redis_client unwraps _backend or returns None for memory."""
    provider = CacheProvider()
    assert provider.get_redis_client() is None

    sentinel = object()
    provider._backends["default"] = _FakeCircuitBreakerWrapper(  # type: ignore[assignment]
        _FakeRedisBackend(sentinel)
    )
    assert provider.get_redis_client("default") is sentinel

    provider._backends["memory"] = object()  # type: ignore[assignment]
    assert provider.get_redis_client("memory") is None
