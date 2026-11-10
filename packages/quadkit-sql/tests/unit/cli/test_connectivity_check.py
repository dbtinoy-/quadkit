"""The SQL CLI contribution must report observed provider health, not a stub."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from quadkit.contracts.core import HealthCheckResult, HealthStatus
from quadkit.contracts.data.sql.database import DatabaseProviderProtocol
from quadkit.sql.cli.checks import check_database_connection
from quadkit.sql.providers.sqlite_provider import SQLiteProvider


@pytest.mark.parametrize("status", list(HealthStatus))
async def test_connectivity_contribution_preserves_provider_evidence(
    status: HealthStatus,
) -> None:
    expected = HealthCheckResult(
        component="database", status=status, message="observed", details={"probe": 1}
    )
    provider = AsyncMock()
    provider.health_check.return_value = expected
    container = AsyncMock()
    container.resolve.return_value = provider

    result = await check_database_connection(container)

    assert result is expected
    container.resolve.assert_awaited_once_with(DatabaseProviderProtocol)
    provider.health_check.assert_awaited_once_with(timeout=5.0)


@pytest.mark.parametrize("phase", ["resolution", "probe"])
@pytest.mark.parametrize("error", [RuntimeError, ValueError, OSError])
async def test_connectivity_failures_cannot_be_success_or_leak_credentials(
    phase: str, error: type[Exception]
) -> None:
    secret = "postgresql://private:password@internal/database"
    provider = AsyncMock()
    container = AsyncMock()
    container.resolve.return_value = provider
    target = container.resolve if phase == "resolution" else provider.health_check
    target.side_effect = error(secret)

    result = await check_database_connection(container)

    assert isinstance(result, HealthCheckResult)
    assert result.status is HealthStatus.UNHEALTHY
    assert result.error
    assert secret not in repr(result)
    if phase == "resolution":
        provider.health_check.assert_not_awaited()


@pytest.mark.parametrize("phase", ["resolution", "probe"])
async def test_caller_cancellation_is_not_swallowed(phase: str) -> None:
    provider = AsyncMock()
    container = AsyncMock()
    container.resolve.return_value = provider
    target = container.resolve if phase == "resolution" else provider.health_check
    target.side_effect = asyncio.CancelledError
    with pytest.raises(asyncio.CancelledError):
        await check_database_connection(container)


async def test_real_sqlite_connectivity_is_probed_and_provider_lifecycle_is_owned_by_app() -> (
    None
):
    provider = SQLiteProvider(":memory:")
    container = AsyncMock()
    container.resolve.return_value = provider
    await provider.connect()
    try:
        result = await check_database_connection(container)
        assert result.status is HealthStatus.HEALTHY
        assert await provider.is_connected()
    finally:
        await provider.disconnect()


@pytest.mark.parametrize("phase", ["resolution", "probe"])
async def test_resolution_and_probe_share_a_bounded_deadline(
    phase: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("quadkit.sql.cli.checks._CONNECTIVITY_TIMEOUT", 0.01)
    provider = AsyncMock()
    container = AsyncMock()
    container.resolve.return_value = provider

    async def blocked(*_args: object, **_kwargs: object) -> None:
        await asyncio.Event().wait()

    target = container.resolve if phase == "resolution" else provider.health_check
    target.side_effect = blocked
    result = await asyncio.wait_for(check_database_connection(container), timeout=1.0)
    assert result.status is HealthStatus.UNHEALTHY
    assert result.error
    target.assert_awaited_once()


@pytest.mark.parametrize("invalid", [None, {"status": "ok"}, True, object()])
async def test_malformed_provider_results_cannot_be_success(invalid: object) -> None:
    provider = AsyncMock()
    provider.health_check.return_value = invalid
    container = AsyncMock()
    container.resolve.return_value = provider
    result = await check_database_connection(container)
    assert result.status is HealthStatus.UNHEALTHY
    assert result.error


def test_contribution_targets_connectivity_callback_without_claiming_migrations() -> (
    None
):
    from importlib import import_module

    from quadkit.sql.cli.contributor import SqlCliContributor

    (contribution,) = SqlCliContributor().get_health_checks()
    module, _, attribute = contribution.check_path.partition(":")
    assert getattr(import_module(module), attribute) is check_database_connection
    assert contribution.critical
    assert contribution.timeout > 5.0
    assert "migration" not in contribution.description.lower()
