"""Unit tests for quadkit.http DI providers."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.contracts.core import ProviderPriority
from quadkit.http.config import HTTPClientConfig
from quadkit.http.di.provider import HTTPProvider


class TestHTTPProviderConstruction:
    def test_zero_config_defers_defaults(self) -> None:
        provider = HTTPProvider()
        assert provider._config is None

    def test_custom_config(self) -> None:
        config = HTTPClientConfig()
        provider = HTTPProvider(config=config)
        assert provider._config is config

    def test_from_config_classmethod(self) -> None:
        config = HTTPClientConfig()
        provider = HTTPProvider.from_config(config)
        assert provider._config is config

    def test_name_attribute(self) -> None:
        provider = HTTPProvider()
        assert provider.name == "http"

    def test_priority_is_infrastructure(self) -> None:
        provider = HTTPProvider()
        assert provider.priority == ProviderPriority.INFRASTRUCTURE

    def test_config_key(self) -> None:
        provider = HTTPProvider()
        assert provider.config_key == "http"

    def test_config_model(self) -> None:
        provider = HTTPProvider()
        assert provider.config_model == HTTPClientConfig


class TestHTTPProviderBoot:
    @pytest.mark.asyncio
    async def test_boot_starts_pool(self) -> None:
        provider = HTTPProvider()

        class FakeResolver:
            async def resolve(self, key: type) -> object:
                raise RuntimeError("not registered")

        await provider.boot(FakeResolver())  # type: ignore[arg-type]
        assert provider._client is not None
        await provider.shutdown()

    @pytest.mark.asyncio
    async def test_boot_twice_creates_new_client(self) -> None:
        provider = HTTPProvider()

        class FakeResolver:
            async def resolve(self, key: type) -> object:
                raise RuntimeError("not registered")

        await provider.boot(FakeResolver())  # type: ignore[arg-type]
        client1 = provider._client

        await provider.shutdown()
        await provider.boot(FakeResolver())  # type: ignore[arg-type]
        assert provider._client is not client1

        await provider.shutdown()

    @pytest.mark.asyncio
    async def test_boot_resolves_retry_policy_when_present(self) -> None:
        provider = HTTPProvider()
        mock_retry = MagicMock()
        mock_retry.execute = AsyncMock(return_value="result")

        class FakeResolver:
            async def resolve(self, key: type) -> object:
                if key.__name__ == "RetryPolicyProtocol":
                    return mock_retry
                raise RuntimeError("not registered")

        await provider.boot(FakeResolver())  # type: ignore[arg-type]
        assert provider._client is not None
        await provider.shutdown()

    @pytest.mark.asyncio
    async def test_boot_resolves_circuit_breaker_when_registry_present(self) -> None:
        provider = HTTPProvider()
        mock_cb = MagicMock()
        mock_cb.state = MagicMock(return_value="closed")

        mock_registry = MagicMock()
        mock_registry.get_or_create = AsyncMock(return_value=mock_cb)

        class FakeResolver:
            async def resolve(self, key: type) -> object:
                if "CircuitBreaker" in key.__name__:
                    return mock_registry
                raise RuntimeError("not registered")

        await provider.boot(FakeResolver())  # type: ignore[arg-type]
        assert provider._client is not None
        await provider.shutdown()

    @pytest.mark.asyncio
    async def test_boot_resolves_resilience_pipeline_when_present(self) -> None:
        provider = HTTPProvider()
        mock_pipeline = MagicMock()

        class FakeResolver:
            async def resolve(self, key: type) -> object:
                if key.__name__ == "ResiliencePipelineProtocol":
                    return mock_pipeline
                raise RuntimeError("not registered")

        await provider.boot(FakeResolver())  # type: ignore[arg-type]
        assert provider._client is not None
        await provider.shutdown()


class TestHTTPProviderShutdown:
    @pytest.mark.asyncio
    async def test_shutdown_sets_client_to_none(self) -> None:
        provider = HTTPProvider()

        class FakeResolver:
            async def resolve(self, key: type) -> object:
                raise RuntimeError("not registered")

        await provider.boot(FakeResolver())  # type: ignore[arg-type]
        assert provider._client is not None

        await provider.shutdown()
        assert provider._client is None

    @pytest.mark.asyncio
    async def test_shutdown_idempotent(self) -> None:
        provider = HTTPProvider()
        await provider.shutdown()
        assert provider._client is None


class TestHTTPProviderHealthCheck:
    @pytest.mark.asyncio
    async def test_healthy_when_pool_started(self) -> None:
        from quadkit.contracts.core import HealthStatus

        provider = HTTPProvider()

        class FakeResolver:
            async def resolve(self, key: type) -> object:
                raise RuntimeError("not registered")

        await provider.boot(FakeResolver())  # type: ignore[arg-type]
        result = await provider.health_check()
        assert result.status == HealthStatus.HEALTHY
        assert result.component == "http"
        await provider.shutdown()

    @pytest.mark.asyncio
    async def test_health_check_passes_timeout(self) -> None:
        provider = HTTPProvider()

        class FakeResolver:
            async def resolve(self, key: type) -> object:
                raise RuntimeError("not registered")

        await provider.boot(FakeResolver())  # type: ignore[arg-type]
        result = await provider.health_check(timeout=1.0)
        assert result.details.get("started") is True
        await provider.shutdown()


class TestHTTPProviderRegister:
    @pytest.mark.asyncio
    async def test_register_binds_both_concrete_and_protocol(self) -> None:
        from quadkit.contracts.web import HTTPClientProtocol
        from quadkit.http.client import HTTPClient

        provider = HTTPProvider()
        registered: dict[type, object] = {}

        class FakeRegistrar:
            def singleton(self, key: type, factory: object) -> None:
                registered[key] = factory

        await provider.register(FakeRegistrar())  # type: ignore[arg-type]

        assert HTTPClient in registered
        assert HTTPClientProtocol in registered