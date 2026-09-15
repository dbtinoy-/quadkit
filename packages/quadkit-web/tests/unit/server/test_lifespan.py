"""Unit tests for ASGI lifespan management"""

from unittest.mock import AsyncMock, patch

import pytest
from starlette.applications import Starlette

from quadkit.web.integrations.setup import lifespan


class TestLifespan:
    """Test ASGI lifespan management."""

    @pytest.mark.asyncio
    async def test_startup_handles_missing_resources_gracefully(self):
        """Test startup handles missing resources gracefully."""
        app = Starlette()

        # Mock all imports to raise ImportError (resources not available)
        with patch("quadkit.web.integrations.setup.logger") as mock_logger:
            async with lifespan(app):
                # Should not raise exceptions
                assert hasattr(app.state, "background_tasks")
                assert len(app.state.background_tasks) == 0
                # Should log debug messages about missing resources
                mock_logger.debug.assert_called()

    @pytest.mark.asyncio
    async def test_shutdown_cleans_up_resources(self):
        """Test shutdown cleans up all resources."""
        app = Starlette()

        # Set up mock resources
        mock_db_pool = AsyncMock()
        mock_redis = AsyncMock()

        app.state.db_pool = mock_db_pool
        app.state.redis_client = mock_redis
        app.state.background_tasks = []  # No tasks for this test

        with patch("quadkit.web.integrations.setup.logger") as mock_logger:
            # Run through lifespan
            async with lifespan(app):
                pass  # Exit immediately

            # Verify cleanup
            mock_db_pool.close.assert_called_once()
            mock_redis.close.assert_called_once()
            # Should log shutdown messages
            mock_logger.info.assert_called()

    @pytest.mark.asyncio
    async def test_shutdown_handles_cleanup_errors_gracefully(self):
        """Test shutdown handles cleanup errors gracefully."""
        app = Starlette()

        # Set up mock resources that raise errors on cleanup
        mock_db_pool = AsyncMock()
        mock_db_pool.close.side_effect = Exception("DB close error")
        mock_redis = AsyncMock()
        mock_redis.close.side_effect = Exception("Redis close error")

        app.state.db_pool = mock_db_pool
        app.state.redis_client = mock_redis
        app.state.background_tasks = []

        with patch("quadkit.web.integrations.setup.logger") as mock_logger:
            # Should not raise exceptions even if cleanup fails
            async with lifespan(app):
                pass

            # Cleanup methods were still called
            mock_db_pool.close.assert_called_once()
            mock_redis.close.assert_called_once()
            # Should log errors
            mock_logger.exception.assert_called()

    @pytest.mark.asyncio
    async def test_background_tasks_handled(self):
        """Test background tasks list is initialized."""
        app = Starlette()

        with patch("quadkit.web.integrations.setup.logger") as mock_logger:
            async with lifespan(app):
                # Should initialize background tasks list
                assert hasattr(app.state, "background_tasks")
                assert isinstance(app.state.background_tasks, list)

    @pytest.mark.asyncio
    async def test_preserves_existing_app_state(self):
        """Test lifespan preserves existing app state."""
        app = Starlette()

        # Set some existing state
        app.state.existing_value = "preserved"
        app.state.db_pool = "existing_pool"

        with patch("quadkit.web.integrations.setup.logger") as mock_logger:
            async with lifespan(app):
                # Existing state should be preserved
                assert app.state.existing_value == "preserved"
                # DB pool should not be overwritten if already exists
                assert app.state.db_pool == "existing_pool"

    @pytest.mark.asyncio
    async def test_lifespan_logging(self):
        """Test lifespan logs startup and shutdown events."""
        app = Starlette()

        with patch("quadkit.web.integrations.setup.logger") as mock_logger:
            async with lifespan(app):
                pass

            # Should log startup and shutdown
            startup_calls = [
                call
                for call in mock_logger.info.call_args_list
                if "Starting" in str(call)
            ]
            shutdown_calls = [
                call
                for call in mock_logger.info.call_args_list
                if "Shutting down" in str(call)
            ]

            assert len(startup_calls) > 0
            assert len(shutdown_calls) > 0

    @pytest.mark.asyncio
    async def test_lifespan_emits_server_hooks(self):
        """Lifespan emits canonical startup and shutdown hooks when wired."""
        from quadkit.hooks import HookRegistry
        from quadkit.web.hooks import WebServerStartedHook, WebServerStoppedHook

        app = Starlette()
        registry = HookRegistry("web-test")
        received: list[tuple[str, object]] = []

        async def capture_started(*, payload: object) -> None:
            received.append(("started", payload))

        async def capture_stopped(*, payload: object) -> None:
            received.append(("stopped", payload))

        registry.register_action("server.started", capture_started)
        registry.register_action("server.stopped", capture_stopped)
        app.state.hook_registry = registry

        async with lifespan(app):
            assert received == [("started", WebServerStartedHook())]

        assert received == [
            ("started", WebServerStartedHook()),
            ("stopped", WebServerStoppedHook()),
        ]
