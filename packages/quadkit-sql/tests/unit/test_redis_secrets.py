import pytest

from unittest.mock import patch

from quadkit.contracts.core import HealthStatus
from quadkit.cache.stores.redis_secrets import RedisError, RedisSecretStore


@pytest.mark.asyncio
async def test_health_check_unhealthy_on_client_error(monkeypatch):
    store = RedisSecretStore("redis://localhost:6379")

    async def _fail():
        raise ConnectionError("boom")

    monkeypatch.setattr(store, "_get_client", _fail)

    result = await store.health_check()

    assert result.status == HealthStatus.UNHEALTHY
    assert result.details["driver"] == "redis"
    assert result.error is not None


@pytest.mark.asyncio
async def test_health_check_logs_exception(monkeypatch):
    store = RedisSecretStore("redis://localhost:6379")

    async def _fail():
        raise ConnectionError("boom")

    monkeypatch.setattr(store, "_get_client", _fail)

    with patch("quadkit.cache.stores.redis_secrets.logger") as mock_logger:
        await store.health_check()

    mock_logger.exception.assert_called_once()
    assert "Redis secret store health check failed" in mock_logger.exception.call_args[0][0]
