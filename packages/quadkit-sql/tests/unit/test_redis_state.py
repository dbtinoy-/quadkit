import pytest

from unittest.mock import patch

from quadkit.contracts.core import HealthStatus
from quadkit.cache.stores.redis_state import RedisError, RedisStateStore


@pytest.mark.asyncio
async def test_health_check_unhealthy_on_client_error(monkeypatch):
    store = RedisStateStore("redis://localhost:6379")

    async def _fail():
        raise ConnectionError("boom")

    monkeypatch.setattr(store, "_get_client", _fail)

    result = await store.health_check()

    assert result.status == HealthStatus.UNHEALTHY
    assert result.details["driver"] == "redis"
    assert result.error is not None


@pytest.mark.asyncio
async def test_health_check_logs_exception(monkeypatch):
    store = RedisStateStore("redis://localhost:6379")

    async def _fail():
        raise ConnectionError("boom")

    monkeypatch.setattr(store, "_get_client", _fail)

    with patch("quadkit.cache.stores.redis_state.logger") as mock_logger:
        await store.health_check()
    
    # Verify logger was called with the expected message
    mock_logger.exception.assert_called_once()
    assert "Redis health check failed" in mock_logger.exception.call_args[0][0]
