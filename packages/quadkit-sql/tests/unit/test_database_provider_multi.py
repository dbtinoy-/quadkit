"""Tests for DatabaseProvider multi-backend registration."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from quadkit.contracts.data.sql.database import DatabaseProviderProtocol
from quadkit.di.container import Container
from quadkit.sql.config import (
    DatabaseBackendConfig,
    DatabaseConfig,
    DatabasePoolConfig,
    NamedDatabaseConfig,
)
from quadkit.sql.di.provider import DatabaseProvider


def _make_multi_config() -> DatabaseConfig:
    """Build a two-backend DatabaseConfig for tests."""
    return DatabaseConfig(
        backends=[
            NamedDatabaseConfig(
                name="primary",
                backend=DatabaseBackendConfig(url="sqlite+aiosqlite:///primary.db"),
                primary=True,
            ),
            NamedDatabaseConfig(
                name="maps",
                backend=DatabaseBackendConfig(url="sqlite+aiosqlite:///maps.db"),
                pool=DatabasePoolConfig(min_size=1, max_size=5),
            ),
        ]
    )


@pytest.mark.asyncio
async def test_multi_backend_registers_named_singletons() -> None:
    """DatabaseProvider registers DatabaseProviderProtocol under each backend name."""
    config = _make_multi_config()
    provider = DatabaseProvider(config=config)
    container = Container()

    with patch("quadkit.sql.di._registration.DatabaseService") as MockDbService:
        mock_primary = MagicMock()
        mock_maps = MagicMock()
        MockDbService.side_effect = [mock_primary, mock_maps]

        await provider.register(container)

    assert container.has("primary")
    assert container.has("maps")


@pytest.mark.asyncio
async def test_multi_backend_primary_registers_unnamed() -> None:
    """Primary backend also binds to the unnamed DatabaseProviderProtocol."""
    config = _make_multi_config()
    provider = DatabaseProvider(config=config)
    container = Container()

    with patch("quadkit.sql.di._registration.DatabaseService") as MockDbService:
        mock_primary = MagicMock()
        mock_maps = MagicMock()
        MockDbService.side_effect = [mock_primary, mock_maps]

        await provider.register(container)

    assert container.has(DatabaseProviderProtocol)


@pytest.mark.asyncio
async def test_single_db_mode_unchanged() -> None:
    """DatabaseProvider with empty backends list uses existing single-DB mode."""
    config = DatabaseConfig(
        backend=DatabaseBackendConfig(url="sqlite+aiosqlite:///test.db")
    )
    provider = DatabaseProvider(config=config)
    container = Container()

    with patch("quadkit.sql.di._registration.DatabaseService") as MockDbService:
        MockDbService.return_value = MagicMock()
        await provider.register(container)

    assert container.has(DatabaseProviderProtocol)
    assert not container.has("primary")


@pytest.mark.asyncio
async def test_multi_backend_boot_connects_all_parallel() -> None:
    """DatabaseProvider.boot() connects all named backends concurrently."""
    from unittest.mock import AsyncMock

    config = _make_multi_config()
    provider = DatabaseProvider(config=config)
    container = Container()

    with patch("quadkit.sql.di._registration.DatabaseService") as MockDbService:
        mock_primary = MagicMock()
        mock_primary.boot = AsyncMock()
        mock_maps = MagicMock()
        mock_maps.boot = AsyncMock()
        MockDbService.side_effect = [mock_primary, mock_maps]

        await provider.register(container)

    # boot() calls .boot() on every entry in _db_services via asyncio.gather
    with patch.object(provider, "_boot_admin_widgets", AsyncMock()):
        await provider.boot(MagicMock())

    mock_primary.boot.assert_awaited_once()
    mock_maps.boot.assert_awaited_once()


@pytest.mark.asyncio
async def test_multi_backend_health_check_returns_worst_status() -> None:
    """DatabaseProvider.health_check() returns UNHEALTHY if any backend is UNHEALTHY."""
    from unittest.mock import AsyncMock

    from quadkit.contracts.core import HealthCheckResult, HealthStatus

    config = _make_multi_config()
    provider = DatabaseProvider(config=config)
    container = Container()

    with patch("quadkit.sql.di._registration.DatabaseService") as MockDbService:
        mock_primary = MagicMock()
        mock_primary.health_check = AsyncMock(
            return_value=HealthCheckResult(component="primary", status=HealthStatus.HEALTHY)
        )
        mock_maps = MagicMock()
        mock_maps.health_check = AsyncMock(
            return_value=HealthCheckResult(
                component="maps", status=HealthStatus.UNHEALTHY
            )
        )
        MockDbService.side_effect = [mock_primary, mock_maps]

        await provider.register(container)

    result = await provider.health_check()

    assert result.status == HealthStatus.UNHEALTHY
