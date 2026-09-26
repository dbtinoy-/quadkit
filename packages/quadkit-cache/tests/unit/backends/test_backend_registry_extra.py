"""Focused tests for the cache backend registry."""

from __future__ import annotations

import re

import pytest

from quadkit.cache import constants as const
from quadkit.cache.backends.memory.backend import MemoryCacheBackend
from quadkit.cache.backends.registry import (
    BackendRegistry,
    MemcachedBackendRegistry,
    MemoryBackendRegistry,
    RedisBackendRegistry,
)


def test_memory_registry_can_create_only_memory() -> None:
    registry = MemoryBackendRegistry()
    assert registry.can_create(const.BACKEND_TYPE_MEMORY)
    assert not registry.can_create(const.BACKEND_TYPE_REDIS)
    assert not registry.can_create(const.BACKEND_TYPE_MEMCACHED)


def test_memory_registry_create_returns_backend() -> None:
    backend = MemoryBackendRegistry().create_backend()
    assert isinstance(backend, MemoryCacheBackend)


def test_redis_registry_can_create_only_redis() -> None:
    registry = RedisBackendRegistry()
    assert registry.can_create(const.BACKEND_TYPE_REDIS)
    assert not registry.can_create(const.BACKEND_TYPE_MEMORY)


def test_redis_registry_create_unavailable_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import quadkit.cache.backends.registry as registry_module

    monkeypatch.setattr(registry_module, "_REDIS_AVAILABLE", False)
    with pytest.raises(ImportError, match=re.escape(const.ERROR_MSG_REDIS_INSTALL)):
        RedisBackendRegistry().create_backend()


def test_memcached_registry_create_unavailable_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import quadkit.cache.backends.registry as registry_module

    monkeypatch.setattr(registry_module, "_MEMCACHED_AVAILABLE", False)
    with pytest.raises(
        ImportError, match=re.escape(const.ERROR_MSG_MEMCACHED_INSTALL)
    ):
        MemcachedBackendRegistry().create_backend()


def test_memcached_registry_can_create_only_memcached() -> None:
    registry = MemcachedBackendRegistry()
    assert registry.can_create(const.BACKEND_TYPE_MEMCACHED)
    assert not registry.can_create(const.BACKEND_TYPE_REDIS)


def test_backend_registry_registers_defaults() -> None:
    registry = BackendRegistry.with_defaults()
    for bt in (
        const.BACKEND_TYPE_MEMORY,
        const.BACKEND_TYPE_REDIS,
        const.BACKEND_TYPE_MEMCACHED,
    ):
        assert registry.get(bt) is not None


def test_backend_registry_register_key_value_form() -> None:
    registry = BackendRegistry.with_defaults()
    registry.register("custom", MemoryBackendRegistry())
    assert isinstance(registry.get("custom"), MemoryBackendRegistry)


def test_backend_registry_register_factory_infers_key() -> None:
    class EmptyBackendRegistry(BackendRegistry):
        def _register_defaults(self) -> None:
            pass

    registry = EmptyBackendRegistry()
    registry.register(MemoryBackendRegistry())
    assert isinstance(registry.get(const.BACKEND_TYPE_MEMORY), MemoryBackendRegistry)


def test_backend_registry_register_unknown_factory_raises() -> None:
    class UnknownFactory:
        def can_create(self, backend_type: str) -> bool:
            return False

        def create_backend(self, **kwargs):  # type: ignore[no-untyped-def]
            raise AssertionError("should never be called")

    with pytest.raises(ValueError, match="Cannot infer backend type key"):
        BackendRegistry.with_defaults().register(UnknownFactory())


def test_backend_registry_get_backend_returns_instance() -> None:
    backend = BackendRegistry.with_defaults().get_backend(const.BACKEND_TYPE_MEMORY)
    assert isinstance(backend, MemoryCacheBackend)


def test_backend_registry_get_backend_unknown_raises() -> None:
    registry = BackendRegistry.with_defaults()
    with pytest.raises(ValueError, match="Unknown cache backend"):
        registry.get_backend("unknown-type")