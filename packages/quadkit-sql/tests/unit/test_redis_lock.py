import pytest

from unittest.mock import patch

from quadkit.contracts.core import HealthStatus
from quadkit.cache.stores.redis_lock import RedisError, RedisLockStore


@pytest.mark.asyncio
async def test_health_check_unhealthy_on_client_error(monkeypatch):
    lock = RedisLockStore("redis://localhost:6379")

    async def _fail():
        raise ConnectionError("boom")

    monkeypatch.setattr(lock, "_get_client", _fail)

    with patch("quadkit.cache.stores.redis_lock.logger") as mock_logger:
        res = await lock.health_check()

    assert res.status == HealthStatus.UNHEALTHY
    assert res.error is not None
    mock_logger.exception.assert_called_once()
    assert "Redis lock store health check failed" in mock_logger.exception.call_args[0][0]
