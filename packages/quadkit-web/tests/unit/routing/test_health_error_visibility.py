import pytest
from quadkit.contracts.core import HealthStatus
from quadkit.web.routing.health_checks import WebHealthChecker


class BadDB:
    async def health_check(self, timeout: float = 5.0):
        raise RuntimeError("db-fail")


class BadCacheBackend:
    async def health_check(self, timeout: float = 5.0):
        raise RuntimeError("redis-fail")


@pytest.mark.asyncio
async def test_db_failure_is_reported_unhealthy():
    checker = WebHealthChecker(db_provider=BadDB())
    resp = await checker.check_health()

    assert resp.components["database"].status == HealthStatus.UNHEALTHY
    assert "db-fail" in (resp.components["database"].message or "")


@pytest.mark.asyncio
async def test_redis_failure_is_reported_unhealthy():
    checker = WebHealthChecker(cache_backend=BadCacheBackend())
    resp = await checker.check_health()

    assert resp.components["redis"].status == HealthStatus.UNHEALTHY
    assert "redis-fail" in (resp.components["redis"].message or "")
