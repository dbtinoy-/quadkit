"""Unit tests for ``InfrastructureHealthProvider``."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from quadkit.contracts.core import HealthCheckResult, HealthStatus, Ok
from quadkit.contracts.data.sql import DatabaseProviderProtocol
from quadkit.contracts.infra.cache.protocols import CacheBackendProtocol
from quadkit.contracts.observability.metrics import HealthCheckRegistryProtocol
from quadkit.di import Container
from quadkit.monitor.health import HealthCheckRegistry, InfrastructureHealthProvider


@pytest.mark.asyncio
async def test_infrastructure_health_provider_handles_result_wrapped_cache() -> None:
    container = Container()
    registry = HealthCheckRegistry()
    db_provider = SimpleNamespace(
        health_check=AsyncMock(
            return_value=HealthCheckResult(
                component="db",
                status=HealthStatus.HEALTHY,
                message="ok",
            )
        )
    )
    store: dict[str, object] = {}

    async def _set(
        key: str, value: object, ttl: int | None = None
    ) -> Ok[bool, Exception]:
        del ttl
        store[key] = value
        return Ok(True)

    async def _get(key: str) -> Ok[object | None, Exception]:
        return Ok(store.get(key))

    async def _delete(key: str) -> Ok[bool, Exception]:
        store.pop(key, None)
        return Ok(True)

    cache_backend = SimpleNamespace(
        set=AsyncMock(side_effect=_set),
        get=AsyncMock(side_effect=_get),
        delete=AsyncMock(side_effect=_delete),
    )

    container.singleton(HealthCheckRegistryProtocol, instance=registry)
    container.singleton(DatabaseProviderProtocol, factory=lambda: db_provider)
    container.singleton(CacheBackendProtocol, factory=lambda: cache_backend)

    await InfrastructureHealthProvider().boot(container)

    status, details = await registry.run_readiness()
    assert status == HealthStatus.HEALTHY
    components = {item["component"] for item in details["checks"]}
    assert {"infra:db", "infra:cache"} <= components
