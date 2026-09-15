"""Tests for the Quadkit pytest plugin (plugins/pytest)."""

from unittest.mock import MagicMock, patch

import pytest

from quadkit.testing.plugins import pytest as plugin


class TestPlugin:
    """Tests for the pytest plugin."""

    def test_pytest_configure_registers_markers(self) -> None:
        """Test pytest_configure registers all markers."""
        mock_config = MagicMock()
        plugin.pytest_configure(mock_config)

        # Verify addinivalue_line was called for each marker
        assert mock_config.addinivalue_line.call_count == len(plugin._MARKERS)

    def test_check_service_redis_available(self) -> None:
        """Test _check_service returns True when Redis is available."""
        with patch("socket.create_connection") as mock_conn:
            mock_conn.return_value.__enter__ = MagicMock(return_value=None)
            mock_conn.return_value.__exit__ = MagicMock(return_value=False)

            result = plugin._check_service("redis")
            assert result is True

    def test_check_service_redis_unavailable(self) -> None:
        """Test _check_service returns False when Redis is unavailable."""
        with patch("socket.create_connection") as mock_conn:
            mock_conn.side_effect = OSError("Connection refused")

            result = plugin._check_service("redis")
            assert result is False

    def test_check_service_unknown_returns_true(self) -> None:
        """Test _check_service returns True for unknown services."""
        result = plugin._check_service("unknown_service")
        assert result is True

    def test_check_service_postgres(self) -> None:
        """Test _check_service for postgres."""
        with patch("socket.create_connection") as mock_conn:
            mock_conn.return_value.__enter__ = MagicMock(return_value=None)
            mock_conn.return_value.__exit__ = MagicMock(return_value=False)

            result = plugin._check_service("postgres")
            assert result is True

    def test_check_service_elasticsearch(self) -> None:
        """Test _check_service for elasticsearch."""
        with patch("socket.create_connection") as mock_conn:
            mock_conn.return_value.__enter__ = MagicMock(return_value=None)
            mock_conn.return_value.__exit__ = MagicMock(return_value=False)

            result = plugin._check_service("elasticsearch")
            assert result is True

    def test_check_service_rabbitmq(self) -> None:
        """Test _check_service for rabbitmq."""
        with patch("socket.create_connection") as mock_conn:
            mock_conn.return_value.__enter__ = MagicMock(return_value=None)
            mock_conn.return_value.__exit__ = MagicMock(return_value=False)

            result = plugin._check_service("rabbitmq")
            assert result is True

    def test_check_service_meilisearch(self) -> None:
        """Test _check_service for meilisearch."""
        with patch("socket.create_connection") as mock_conn:
            mock_conn.return_value.__enter__ = MagicMock(return_value=None)
            mock_conn.return_value.__exit__ = MagicMock(return_value=False)

            result = plugin._check_service("meilisearch")
            assert result is True

    def test_check_service_smtp(self) -> None:
        """Test _check_service for smtp."""
        with patch("socket.create_connection") as mock_conn:
            mock_conn.return_value.__enter__ = MagicMock(return_value=None)
            mock_conn.return_value.__exit__ = MagicMock(return_value=False)

            result = plugin._check_service("smtp")
            assert result is True

    def test_pytest_collection_modifyitems_no_markers(self) -> None:
        """Test pytest_collection_modifyitems with no special markers."""
        mock_config = MagicMock()
        mock_item = MagicMock()
        mock_item.iter_markers.return_value = []

        plugin.pytest_collection_modifyitems(mock_config, [mock_item])

        # No skip marker should be added
        mock_item.add_marker.assert_not_called()

    def test_pytest_collection_modifyitems_with_requires_marker(
        self,
    ) -> None:
        """Test pytest_collection_modifyitems adds skip for unavailable service."""
        mock_config = MagicMock()
        mock_item = MagicMock()
        mock_marker = MagicMock()
        mock_marker.name = "requires_redis"

        with patch.object(plugin, "_check_service", return_value=False):
            mock_item.iter_markers.return_value = [mock_marker]
            plugin.pytest_collection_modifyitems(mock_config, [mock_item])

            # Skip marker should be added
            mock_item.add_marker.assert_called_once()

    def test_pytest_collection_modifyitems_non_requires_marker(
        self,
    ) -> None:
        """Test pytest_collection_modifyitems ignores non-requires markers."""
        mock_config = MagicMock()
        mock_item = MagicMock()
        mock_marker = MagicMock()
        mock_marker.name = "integration"

        mock_item.iter_markers.return_value = [mock_marker]
        plugin.pytest_collection_modifyitems(mock_config, [mock_item])

        # No skip marker should be added
        mock_item.add_marker.assert_not_called()

    def test_service_endpoints_defined(self) -> None:
        """Test that all expected service endpoints are defined."""
        expected_services = [
            "redis",
            "postgres",
            "elasticsearch",
            "rabbitmq",
            "meilisearch",
            "smtp",
        ]
        for service in expected_services:
            assert service in plugin._SERVICE_ENDPOINTS

    def test_markers_defined(self) -> None:
        """Test that all expected markers are defined."""
        expected_markers = [
            "requires_redis",
            "requires_postgres",
            "requires_elasticsearch",
            "requires_rabbitmq",
            "requires_meilisearch",
            "requires_smtp",
            "integration",
            "slow",
            "performance",
        ]
        for marker in expected_markers:
            assert any(marker in m for m in plugin._MARKERS)
