"""Tests for StorageProvider Named DI multi-backend support."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from quadkit.contracts import BlobStoreProtocol
from quadkit.storage.config import NamedStorageConfig, StorageConfig
from quadkit.storage.di.provider import StorageProvider


def _make_config(*names: str) -> StorageConfig:
    backends = [
        NamedStorageConfig(name=n, driver="memory", primary=(i == 0))
        for i, n in enumerate(names)
    ]
    return StorageConfig(backends=backends)


class TestStorageProviderMultiBackend:
    @pytest.mark.asyncio
    async def test_named_bindings_registered_per_backend(self) -> None:
        """register() creates Named binding for every backend."""
        cfg = _make_config("primary", "avatars")
        provider = StorageProvider(config=cfg)
        container = MagicMock()
        container.singleton = MagicMock()

        with patch("quadkit.storage.backends.registry.DriverRegistry.get_driver",
                   return_value=MagicMock()):
            await provider.register(container)

        names = [c.kwargs.get("name") for c in container.singleton.call_args_list]
        assert "primary" in names
        assert "avatars" in names

    @pytest.mark.asyncio
    async def test_primary_gets_unnamed_binding(self) -> None:
        """Primary backend also receives the unnamed BlobStoreProtocol binding."""
        cfg = _make_config("primary", "avatars")
        provider = StorageProvider(config=cfg)
        container = MagicMock()
        container.singleton = MagicMock()

        with patch("quadkit.storage.backends.registry.DriverRegistry.get_driver",
                   return_value=MagicMock()):
            await provider.register(container)

        unnamed = [c for c in container.singleton.call_args_list if c.kwargs.get("name") is None]
        assert len(unnamed) >= 1

    @pytest.mark.asyncio
    async def test_boot_runs_health_checks_in_parallel(self) -> None:
        """boot() health-checks all drivers via asyncio.gather."""
        cfg = _make_config("primary", "avatars")
        provider = StorageProvider(config=cfg)
        container = MagicMock()
        container.singleton = MagicMock()

        from quadkit.contracts import HealthCheckResult, HealthStatus
        healthy = HealthCheckResult(component="storage", status=HealthStatus.HEALTHY, duration_ms=1.0)
        mock_driver = MagicMock()
        mock_driver.health_check = AsyncMock(return_value=healthy)

        with patch("quadkit.storage.backends.registry.DriverRegistry.get_driver",
                   return_value=mock_driver):
            await provider.register(container)
            await provider.boot(container)

        assert mock_driver.health_check.await_count == 2  # one per backend

    @pytest.mark.asyncio
    async def test_shutdown_closes_in_reverse(self) -> None:
        """shutdown() closes backends in reverse registration order."""
        cfg = _make_config("primary", "avatars")
        provider = StorageProvider(config=cfg)
        container = MagicMock()
        container.singleton = MagicMock()
        call_order: list[str] = []

        mock1 = MagicMock()
        mock1.close = AsyncMock(side_effect=lambda: call_order.append("primary"))
        mock1.health_check = AsyncMock(return_value=MagicMock(status=MagicMock()))
        mock2 = MagicMock()
        mock2.close = AsyncMock(side_effect=lambda: call_order.append("avatars"))
        mock2.health_check = AsyncMock(return_value=MagicMock(status=MagicMock()))

        with patch("quadkit.storage.backends.registry.DriverRegistry.get_driver",
                   side_effect=[mock1, mock2]):
            await provider.register(container)
            await provider.shutdown()

        assert call_order == ["avatars", "primary"]

    @pytest.mark.asyncio
    async def test_single_backend_path_unchanged(self) -> None:
        """Single-backend path (no backends list) still works."""
        cfg = StorageConfig(default_driver="memory")
        provider = StorageProvider(config=cfg)
        container = MagicMock()
        container.singleton = MagicMock()

        await provider.register(container)

        # DriverRegistry + BlobStoreProtocol unnamed = 2 calls minimum
        assert container.singleton.call_count >= 2
