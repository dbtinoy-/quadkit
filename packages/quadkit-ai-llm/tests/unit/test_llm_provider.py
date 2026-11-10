"""Unit tests for LLMProvider."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.ai.llm.config import PricingConfig
from quadkit.ai.llm.di.provider import LLMProvider
from quadkit.contracts.ai.llm import CostEstimatorProtocol
from quadkit.contracts.core.provider import ProviderPriority
from quadkit.contracts.web.http_models import HttpStatusError
from quadkit.di.provider import Provider


class TestLLMProviderStructure:
    """Test LLMProvider class structure and attributes."""

    def test_provider_class_exists(self) -> None:
        """Verify LLMProvider class exists and can be instantiated."""
        prov = LLMProvider()
        assert prov is not None
        assert isinstance(prov, LLMProvider)

    def test_provider_name(self) -> None:
        """Verify provider has correct name attribute."""
        prov = LLMProvider()
        assert prov.name == "llm"

    def test_provider_priority(self) -> None:
        """Verify provider has DOMAIN priority."""
        prov = LLMProvider()
        assert prov.priority == ProviderPriority.DOMAIN

    def test_provider_is_provider_subclass(self) -> None:
        """Verify LLMProvider is a proper Provider subclass."""
        assert issubclass(LLMProvider, Provider)

    def test_provider_has_required_methods(self) -> None:
        """Verify provider has all required lifecycle methods."""
        prov = LLMProvider()
        assert hasattr(prov, "register")
        assert callable(prov.register)
        assert hasattr(prov, "boot")
        assert callable(prov.boot)
        assert hasattr(prov, "shutdown")
        assert callable(prov.shutdown)


class TestLLMProviderLifecycle:
    """Test LLMProvider lifecycle methods."""

    @pytest.mark.asyncio
    async def test_register_method_signature(self) -> None:
        """Verify register() method has correct async signature."""
        prov = LLMProvider()
        container = MagicMock()
        container.singleton = MagicMock()

        # Should complete without error
        await prov.register(container)

    @pytest.mark.asyncio
    async def test_boot_method_signature(self) -> None:
        """Verify boot() method has correct async signature."""
        prov = LLMProvider()
        container = MagicMock()
        container.resolve = AsyncMock()
        container.resolve_optional = AsyncMock()

        # Should complete without error
        await prov.boot(container)

    @pytest.mark.asyncio
    async def test_shutdown_method_signature(self) -> None:
        """Verify shutdown() method has correct async signature."""
        prov = LLMProvider()

        # Should complete without error
        await prov.shutdown()


class _FakeCacheBackend:
    """In-memory ``CacheBackendProtocol`` double."""

    def __init__(self) -> None:
        self.store: dict[str, object] = {}

    async def get(self, key: str):
        from quadkit.contracts.core.result import Ok

        return Ok(self.store.get(key))

    async def set(self, key: str, value: object, *args: object, **kwargs: object):
        from quadkit.contracts.core.result import Ok

        self.store[key] = value
        return Ok(True)

    async def delete(self, key: str):
        from quadkit.contracts.core.result import Ok

        self.store.pop(key, None)
        return Ok(True)

    async def delete_many(self, keys: list[str]):
        from quadkit.contracts.core.result import Ok

        return Ok(0)

    async def delete_pattern(self, pattern: str):
        from quadkit.contracts.core.result import Ok

        return Ok(0)

    async def exists(self, key: str):
        from quadkit.contracts.core.result import Ok

        return Ok(key in self.store)

    async def get_many(self, keys: list[str]):
        from quadkit.contracts.core.result import Ok

        return Ok({k: self.store[k] for k in keys if k in self.store})

    async def set_many(self, mapping: dict, *args: object, **kwargs: object):
        from quadkit.contracts.core.result import Ok

        self.store.update(mapping)
        return Ok(len(mapping))

    async def health_check(self, timeout: float = 5.0):
        from quadkit.contracts.core import HealthCheckResult, HealthStatus

        return HealthCheckResult(
            component="fake-cache", status=HealthStatus.HEALTHY, details={}
        )

    async def clear(self, *args: object, **kwargs: object):
        from quadkit.contracts.core.result import Ok

        self.store.clear()
        return Ok(None)


def _cache_config() -> ClientConfig:
    """A client config with response caching enabled (no backend injected)."""
    from quadkit.ai.llm.config import ClientConfig

    return ClientConfig(
        provider="openai",
        model="gpt-4",
        api_key="sk-test-12345",
        enable_cache=True,
    )


def _cache_provider(**kwargs: Any) -> LLMProvider:
    """Caching-enabled provider built without a real SDK.

    The deferred-cache logic is client-agnostic; ``stub_mode`` keeps the
    tests hermetic so they pass with or without the optional openai SDK
    installed. (A missing SDK makes register() degrade to
    ``llm_client_skipped`` before the cache wiring — correct provider
    behaviour, but out of scope for these tests.)
    """
    kwargs.setdefault("stub_mode", True)
    return LLMProvider(_cache_config(), **kwargs)


class TestDeferredCacheBinding:
    """Cache backend resolution is deferred from register() to boot().

    The orchestrator registers sub-providers before the container is
    booted (and frozen), so a container-resolved cache backend is not
    available at register() time. The wrapper is registered against a
    pass-through cache and bound to the real backend in boot().
    """

    @pytest.mark.asyncio
    async def test_register_defers_cache_when_no_backend(self) -> None:
        """register() with enable_cache=True and no injected backend must not raise."""
        from quadkit.ai.llm.caching.core import NoOpLLMCache
        from quadkit.di.container.container import Container

        provider = _cache_provider()
        container = Container()
        await provider.register(container)

        assert provider._cache_deferred is True
        llm_cache = await container.resolve("llm_cache")
        assert isinstance(llm_cache, NoOpLLMCache)
        # The client is still registered and resolvable.
        assert provider.llm_client is not None

    @pytest.mark.asyncio
    async def test_boot_binds_cache_from_container(self) -> None:
        """boot() resolves the container cache backend and binds it into the wrapper."""
        from quadkit.ai.llm.caching.core import RedisLLMCache
        from quadkit.contracts.infra.cache import CacheBackendProtocol
        from quadkit.di.container.container import Container

        provider = _cache_provider()
        container = Container()
        backend = _FakeCacheBackend()
        container.singleton(CacheBackendProtocol, backend)
        await provider.register(container)

        await provider.boot(container)

        assert provider._cache_deferred is False
        assert provider.cache_backend is backend
        # The registered wrapper (unchanged binding) now caches via the backend.
        assert provider._cache_wrapper is not None
        assert isinstance(provider._cache_wrapper._cache, RedisLLMCache)  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_boot_raises_when_cache_enabled_but_no_backend(self) -> None:
        """enable_cache=True with no backend anywhere must fail boot loudly."""
        from quadkit.di.container.container import Container

        provider = _cache_provider()
        container = Container()
        await provider.register(container)

        with pytest.raises(ValueError, match="CacheBackendProtocol"):
            await provider.boot(container)

    @pytest.mark.asyncio
    async def test_injected_backend_binds_eagerly_at_register(self) -> None:
        """A constructor-injected backend keeps the pre-existing eager path."""
        from quadkit.ai.llm.caching.core import RedisLLMCache

        provider = _cache_provider(cache_backend=_FakeCacheBackend())
        container = MagicMock()
        container.singleton = MagicMock()

        await provider.register(container)

        assert provider._cache_deferred is False
        assert provider._cache_wrapper is not None
        assert isinstance(provider._cache_wrapper._cache, RedisLLMCache)  # type: ignore[attr-defined]


class TestPricingBootContainment:
    """LLMProvider.boot must survive pricing warm() failures."""

    @pytest.mark.asyncio
    async def test_boot_survives_pricing_warm_http_error(self) -> None:
        """An HTTP error during pricing warm-up must not abort boot."""
        from quadkit.ai.llm.pricing.estimator import PricingCostEstimator

        prov = LLMProvider()
        prov.config.pricing = PricingConfig(enabled=True, sources=[])

        async def _raise_http_error(*args: object) -> None:
            raise HttpStatusError("boom", status=503, response=MagicMock())

        estimator = PricingCostEstimator({})
        estimator.warm = _raise_http_error  # type: ignore[method-assign]

        async def _resolve(key: object) -> object:
            if key is CostEstimatorProtocol:
                return estimator
            return MagicMock()

        container = MagicMock()
        container.resolve = AsyncMock(side_effect=_resolve)
        container.resolve_optional = AsyncMock()

        # Must complete without raising.
        await prov.boot(container)

        assert container.resolve_optional is not None
