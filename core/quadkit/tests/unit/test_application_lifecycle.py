"""Tests for ApplicationLifecycle collaborator."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from quadkit.app.base import Application, AppState
from quadkit.app.lifecycle import ApplicationLifecycle


class TestApplicationLifecycleInstantiation:
    """ApplicationLifecycle should be instantiable with required dependencies."""

    def test_creates_with_container_and_orchestrator(self) -> None:
        """Should accept container, orchestrator, config, logger, and app_name."""
        from quadkit.config import QuadkitConfig
        from quadkit.di.container import Container
        from quadkit.di.orchestrator import ProviderOrchestrator
        from quadkit.logging import get_logger

        container = Container()
        orchestrator = ProviderOrchestrator(container)
        config = QuadkitConfig()
        logger = get_logger("test")

        lifecycle = ApplicationLifecycle(
            container=container,
            orchestrator=orchestrator,
            config=config,
            logger=logger,
            app_name="test-app",
        )

        assert lifecycle is not None
        assert lifecycle._app_name == "test-app"


class TestApplicationLifecycleBoot:
    """ApplicationLifecycle.boot should orchestrate provider boot sequence."""

    @pytest.mark.asyncio
    async def test_boot_sets_start_time(self) -> None:
        """Boot should record start time for uptime tracking."""
        from quadkit.config import QuadkitConfig
        from quadkit.di.container import Container
        from quadkit.di.orchestrator import ProviderOrchestrator
        from quadkit.logging import get_logger

        container = Container()
        orchestrator = ProviderOrchestrator(container)
        config = QuadkitConfig()
        logger = get_logger("test")

        lifecycle = ApplicationLifecycle(
            container=container,
            orchestrator=orchestrator,
            config=config,
            logger=logger,
            app_name="test-app",
        )

        await lifecycle.boot()

        assert lifecycle._start_time is not None

    @pytest.mark.asyncio
    async def test_boot_calls_orchestrator_boot_all(self) -> None:
        """Boot should delegate to orchestrator.boot_all."""
        from quadkit.config import QuadkitConfig
        from quadkit.di.container import Container
        from quadkit.di.orchestrator import ProviderOrchestrator
        from quadkit.logging import get_logger

        container = Container()
        orchestrator = ProviderOrchestrator(container)
        config = QuadkitConfig()
        logger = get_logger("test")

        lifecycle = ApplicationLifecycle(
            container=container,
            orchestrator=orchestrator,
            config=config,
            logger=logger,
            app_name="test-app",
        )

        orchestrator.boot_all = AsyncMock()

        await lifecycle.boot()

        orchestrator.boot_all.assert_awaited_once_with(container)


class TestApplicationLifecycleShutdown:
    """ApplicationLifecycle.shutdown should orchestrate provider shutdown."""

    @pytest.mark.asyncio
    async def test_shutdown_disposes_container(self) -> None:
        """Shutdown should dispose the container."""
        from quadkit.config import QuadkitConfig
        from quadkit.di.container import Container
        from quadkit.di.orchestrator import ProviderOrchestrator
        from quadkit.logging import get_logger

        container = Container()
        orchestrator = ProviderOrchestrator(container)
        config = QuadkitConfig()
        logger = get_logger("test")

        lifecycle = ApplicationLifecycle(
            container=container,
            orchestrator=orchestrator,
            config=config,
            logger=logger,
            app_name="test-app",
        )

        container.dispose = AsyncMock()

        await lifecycle.shutdown()

        container.dispose.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_shutdown_calculates_uptime(self) -> None:
        """Shutdown should calculate uptime from start_time."""
        from quadkit.config import QuadkitConfig
        from quadkit.di.container import Container
        from quadkit.di.orchestrator import ProviderOrchestrator
        from quadkit.logging import get_logger

        container = Container()
        orchestrator = ProviderOrchestrator(container)
        config = QuadkitConfig()
        logger = get_logger("test")

        lifecycle = ApplicationLifecycle(
            container=container,
            orchestrator=orchestrator,
            config=config,
            logger=logger,
            app_name="test-app",
        )

        lifecycle._start_time = 100.0

        await lifecycle.shutdown()

        assert lifecycle._uptime_seconds is not None
        assert lifecycle._uptime_seconds >= 0


class TestApplicationDelegatesToLifecycle:
    """Application should delegate boot/shutdown to ApplicationLifecycle."""

    @pytest.mark.asyncio
    async def test_application_uses_lifecycle_for_start(self) -> None:
        """Application.start should delegate to lifecycle.boot."""
        app = Application()

        with patch.object(app._lifecycle, "boot", new_callable=AsyncMock) as mock_boot:
            await app.start()

            mock_boot.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_application_uses_lifecycle_for_stop(self) -> None:
        """Application.stop should delegate to lifecycle.shutdown."""
        app = Application()
        app._state = AppState.RUNNING

        with patch.object(
            app._lifecycle, "shutdown", new_callable=AsyncMock
        ) as mock_shutdown:
            await app.stop()

            mock_shutdown.assert_awaited_once()


class TestApplicationShutdownTimeout:
    """Application.stop should bound shutdown via AppConfig.shutdown_timeout."""

    @pytest.mark.asyncio
    async def test_stop_raises_when_shutdown_exceeds_timeout(self) -> None:
        """A shutdown exceeding the configured timeout aborts with AppShutdownError."""
        import asyncio

        from quadkit.app.exceptions import AppShutdownError
        from quadkit.config import QuadkitConfig

        app = Application()
        app._state = AppState.RUNNING
        app._config = QuadkitConfig(app={"shutdown_timeout": 0.05})

        async def slow_shutdown() -> None:
            await asyncio.sleep(5)

        with patch.object(app._lifecycle, "shutdown", new=slow_shutdown):
            with pytest.raises(AppShutdownError, match="timed out"):
                await app.stop()

        assert app._state == AppState.STOPPED

    @pytest.mark.asyncio
    async def test_stop_within_timeout_succeeds(self) -> None:
        """A fast shutdown is unaffected by the timeout bound."""
        from quadkit.config import QuadkitConfig

        app = Application()
        app._state = AppState.RUNNING
        app._config = QuadkitConfig(app={"shutdown_timeout": 30.0})

        with patch.object(
            app._lifecycle, "shutdown", new_callable=AsyncMock
        ) as mock_shutdown:
            await app.stop()

        mock_shutdown.assert_awaited_once()
        assert app._state == AppState.STOPPED

    @pytest.mark.asyncio
    async def test_stop_uses_default_when_timeout_is_missing(self) -> None:
        """A missing nested timeout must not reach float() as None."""
        from quadkit.app.constants import DEFAULT_SHUTDOWN_TIMEOUT
        from quadkit.config import QuadkitConfig

        app = Application()
        app._state = AppState.RUNNING
        app._config = QuadkitConfig(app={})

        async def passthrough(awaitable: object, *, timeout: float) -> None:
            await awaitable  # type: ignore[misc]

        wait_for = AsyncMock(side_effect=passthrough)
        with patch.object(
            app._lifecycle, "shutdown", new_callable=AsyncMock
        ) as mock_shutdown:
            with patch("quadkit.app.base.asyncio.wait_for", new=wait_for):
                await app.stop()

        wait_for.assert_awaited_once()
        assert wait_for.call_args.kwargs["timeout"] == DEFAULT_SHUTDOWN_TIMEOUT
        mock_shutdown.assert_awaited_once()
        assert app._state == AppState.STOPPED
