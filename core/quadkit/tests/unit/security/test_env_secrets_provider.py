"""Unit tests for EnvSecretsProvider."""

from __future__ import annotations

import pytest

from quadkit.config import QuadkitConfig
from quadkit.contracts.core.config import Environment
from quadkit.contracts.core.health import HealthStatus
from quadkit.contracts.security import SecretNotFoundError, SecretStoreProtocol
from quadkit.di.container import Container
from quadkit.security import EnvSecretsProvider, EnvSecretStore


@pytest.mark.asyncio
async def test_env_secrets_provider_registers_concrete_and_protocol_store(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_API_KEY", "secret-val")
    container = Container()
    provider = EnvSecretsProvider(required_keys=["APP_API_KEY"])

    await provider.register(container)
    await provider.boot(container)

    concrete = await container.resolve(EnvSecretStore)
    proto = await container.resolve(SecretStoreProtocol)
    assert concrete is proto
    assert str(proto.get_secret("APP_API_KEY")) == "secret-val"
    # clear_after_read defaults to False so multi-consumer reads remain stable
    assert proto.has_secret("APP_API_KEY") is True

    health = await provider.health_check()
    assert health.status == HealthStatus.HEALTHY


@pytest.mark.asyncio
async def test_env_secrets_provider_fails_closed_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MISSING_PROD_SECRET", raising=False)
    container = Container()
    container.singleton(
        QuadkitConfig,
        QuadkitConfig(env=Environment.PRODUCTION, debug=False),
    )
    provider = EnvSecretsProvider(required_keys=["MISSING_PROD_SECRET"])

    await provider.register(container)
    with pytest.raises(SecretNotFoundError, match="MISSING_PROD_SECRET"):
        await provider.boot(container)


@pytest.mark.asyncio
async def test_env_secrets_provider_warns_only_in_development(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MISSING_DEV_SECRET", raising=False)
    container = Container()
    container.singleton(
        QuadkitConfig,
        QuadkitConfig(env=Environment.DEVELOPMENT),
    )
    provider = EnvSecretsProvider(required_keys=["MISSING_DEV_SECRET"])

    await provider.register(container)
    await provider.boot(container)

    health = await provider.health_check()
    assert health.status == HealthStatus.DEGRADED
