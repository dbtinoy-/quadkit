"""Health responses and logs must not expose dependency exception details."""

from unittest.mock import MagicMock

import pytest

from quadkit.contracts.core import HealthCheckResult, HealthStatus
import quadkit.web.routing.health_checks as health_checks_module
from quadkit.web.routing.health_checks import WebHealthChecker

_PRIVATE_ERROR = "PRIVATE_DB_ERROR_SENTINEL at /srv/private/tenant-db.db"


class BadDB:
    async def health_check(self, timeout: float = 5.0):
        raise RuntimeError(_PRIVATE_ERROR)


class BadCacheBackend:
    async def health_check(self, timeout: float = 5.0):
        raise RuntimeError(_PRIVATE_ERROR)


class UnhealthyDB:
    async def health_check(self, timeout: float = 5.0):
        return HealthCheckResult(
            component="database",
            status=HealthStatus.UNHEALTHY,
            message=_PRIVATE_ERROR,
        )


@pytest.mark.asyncio
async def test_db_failure_omits_exception_text_from_health_and_logs(monkeypatch):
    logger = MagicMock()
    monkeypatch.setattr(health_checks_module, "logger", logger)
    checker = WebHealthChecker(db_provider=BadDB())

    resp = await checker.check_health()

    assert resp.components["database"].status == HealthStatus.UNHEALTHY
    assert resp.components["database"].message == "Database health check failed"
    captured = repr(logger.mock_calls)
    assert "RuntimeError" in captured
    assert _PRIVATE_ERROR not in captured
    assert "/srv/private/tenant-db.db" not in captured
    logger.error.assert_called_once_with(
        "database_health_check_failed",
        error_type="RuntimeError",
    )
    logger.exception.assert_not_called()


@pytest.mark.asyncio
async def test_cache_failure_omits_exception_text_from_health_and_logs(monkeypatch):
    logger = MagicMock()
    monkeypatch.setattr(health_checks_module, "logger", logger)
    checker = WebHealthChecker(cache_backend=BadCacheBackend())

    resp = await checker.check_health()

    assert resp.components["redis"].status == HealthStatus.UNHEALTHY
    assert resp.components["redis"].message == "Cache health check failed"
    captured = repr(logger.mock_calls)
    assert "RuntimeError" in captured
    assert _PRIVATE_ERROR not in captured
    assert "/srv/private/tenant-db.db" not in captured
    logger.error.assert_called_once_with(
        "cache_health_check_failed",
        error_type="RuntimeError",
    )
    logger.exception.assert_not_called()


@pytest.mark.asyncio
async def test_unhealthy_provider_message_is_not_exposed():
    checker = WebHealthChecker(db_provider=UnhealthyDB())

    resp = await checker.check_health()

    assert resp.components["database"].message == "Database unhealthy"
    assert _PRIVATE_ERROR not in resp.components["database"].message
