"""Tests for contracts resources protocols."""

import pytest
from unittest.mock import AsyncMock, MagicMock


class TestResourceProtocols:
    """Tests for resource protocols."""

    def test_pool_stats_protocol_import(self) -> None:
        """Test PoolStats can be imported."""
        from quadkit.contracts.infra.resources import PoolStatsProtocol

        assert PoolStatsProtocol is not None

    def test_pool_stats_is_protocol(self) -> None:
        """Test PoolStatsProtocol is a Protocol."""
        from quadkit.contracts.infra.resources import PoolStatsProtocol

        # PoolStats should be a Protocol
        assert hasattr(PoolStatsProtocol, "__protocol_attrs__") or hasattr(PoolStatsProtocol, "__annotations__") or hasattr(PoolStatsProtocol, "__annotations__")


class TestPoolProtocol:
    """Tests for PoolProtocol."""

    def test_pool_protocol_import(self) -> None:
        """Test PoolProtocol can be imported."""
        from quadkit.contracts.infra.resources import PoolProtocol

        assert PoolProtocol is not None

    def test_pool_protocol_methods(self) -> None:
        """Test PoolProtocol has expected methods."""
        from quadkit.contracts.infra.resources import PoolProtocol

        # Verify protocol has the required methods
        assert hasattr(PoolProtocol, "get_stats")
        assert hasattr(PoolProtocol, "close")


class TestPoolManagerProtocol:
    """Tests for PoolManagerProtocol."""

    def test_pool_manager_protocol_import(self) -> None:
        """Test PoolManagerProtocol can be imported."""
        from quadkit.contracts.infra.resources import PoolManagerProtocol

        assert PoolManagerProtocol is not None

    def test_pool_manager_protocol_methods(self) -> None:
        """Test PoolManagerProtocol has expected methods."""
        from quadkit.contracts.infra.resources import PoolManagerProtocol

        # Verify protocol has the required methods
        assert hasattr(PoolManagerProtocol, "get_stats")
        assert hasattr(PoolManagerProtocol, "get_pool")


class TestResourcesExport:
    """Tests for resources module exports."""

    def test_resources_exports(self) -> None:
        """Test resources module exports."""
        from quadkit.contracts.infra import resources

        assert resources is not None
