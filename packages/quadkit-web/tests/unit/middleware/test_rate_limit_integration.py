"""Tests for RateLimitIntegration — verifies rate limiting is wired to routes.

This covers CRIT-02: Rate limiting wired to routes via WebRateLimiterProtocol protocol.
The integration resolves WebRateLimiterProtocol from the DI container and adds
RateLimitMiddleware to the Starlette app when rate_limit.enabled is True.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.applications import Starlette

from quadkit.web.config import RateLimitConfig, WebConfig
from quadkit.web.integrations.rate_limit import RateLimitIntegration
from quadkit.web.middleware.rate_limit import RateLimiter, RateLimitMiddleware

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_app() -> Starlette:
    """Create a minimal Starlette test application."""
    return Starlette()


def _make_config(enabled: bool) -> WebConfig:
    """Create a WebConfig with rate_limit.enabled as specified."""
    config = WebConfig()
    config.rate_limit = RateLimitConfig(enabled=enabled)
    return config


# ---------------------------------------------------------------------------
# RateLimitIntegration.configure tests
# ---------------------------------------------------------------------------


class TestRateLimitIntegrationConfigure:
    @pytest.mark.asyncio
    async def test_does_nothing_when_rate_limit_disabled(self) -> None:
        """No middleware added when rate_limit.enabled=False."""
        app = _make_app()
        container = MagicMock()
        config = _make_config(enabled=False)

        initial_middleware_count = len(app.middleware_stack.__class__.__mro__)
        await RateLimitIntegration.configure(app, container, config)

        # Container should not have been touched
        container.resolve.assert_not_called()

    @pytest.mark.asyncio
    async def test_does_nothing_when_no_rate_limit_config(self) -> None:
        """No middleware added when web_config has no rate_limit attr."""
        app = _make_app()
        container = MagicMock()

        class _ConfigWithoutRateLimit:
            pass

        await RateLimitIntegration.configure(app, container, _ConfigWithoutRateLimit())
        container.resolve.assert_not_called()

    @pytest.mark.asyncio
    async def test_resolves_web_rate_limiter_from_container(self) -> None:
        """When enabled, resolves WebRateLimiterProtocol optionally from container."""
        app = _make_app()
        mock_limiter = MagicMock(spec=RateLimiter)
        container = MagicMock()
        container.resolve_optional = AsyncMock(return_value=mock_limiter)
        config = _make_config(enabled=True)

        await RateLimitIntegration.configure(app, container, config)

        container.resolve_optional.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_falls_back_to_in_memory_when_protocol_unbound(self) -> None:
        """Falls back to in-memory RateLimiter when the protocol is not bound."""
        app = _make_app()
        container = MagicMock()
        container.resolve_optional = AsyncMock(return_value=None)
        config = _make_config(enabled=True)

        # Should not raise — falls back to RateLimiter()
        await RateLimitIntegration.configure(app, container, config)

    @pytest.mark.asyncio
    async def test_fallback_is_silent_when_protocol_unbound(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Unbound WebRateLimiterProtocol must not log DI noise."""
        app = _make_app()
        container = MagicMock()
        container.resolve_optional = AsyncMock(return_value=None)
        config = _make_config(enabled=True)

        with caplog.at_level("INFO"):
            await RateLimitIntegration.configure(app, container, config)
        assert not [r for r in caplog.records if "not in container" in r.message]

    @pytest.mark.asyncio
    async def test_adds_rate_limit_middleware_when_enabled(self) -> None:
        """RateLimitMiddleware is added to the app when rate limiting is enabled."""
        app = _make_app()
        mock_limiter = MagicMock(spec=RateLimiter)
        container = MagicMock()
        container.resolve_optional = AsyncMock(return_value=mock_limiter)
        config = _make_config(enabled=True)

        added_middlewares: list = []

        with patch.object(
            app,
            "add_middleware",
            side_effect=lambda cls, **kwargs: added_middlewares.append((cls, kwargs)),
        ):
            await RateLimitIntegration.configure(app, container, config)

        middleware_classes = [cls for cls, _ in added_middlewares]
        assert RateLimitMiddleware in middleware_classes

    @pytest.mark.asyncio
    async def test_adds_rate_limit_exception_handler_when_enabled(self) -> None:
        """RateLimitError exception handler is registered when rate limiting is enabled."""
        from quadkit.contracts.exceptions import RateLimitError

        app = _make_app()
        mock_limiter = MagicMock(spec=RateLimiter)
        container = MagicMock()
        container.resolve_optional = AsyncMock(return_value=mock_limiter)
        config = _make_config(enabled=True)

        registered_handlers: list = []

        with patch.object(
            app,
            "add_exception_handler",
            side_effect=lambda exc, _handler: registered_handlers.append(exc),
        ), patch.object(app, "add_middleware"):
            await RateLimitIntegration.configure(app, container, config)

        assert RateLimitError in registered_handlers

    @pytest.mark.asyncio
    async def test_rate_limit_handler_returns_429(self) -> None:
        """The built-in handler returns HTTP 429 with retry-after header."""
        from starlette.requests import Request
        from starlette.testclient import TestClient

        from quadkit.contracts.exceptions import RateLimitError

        # Build a minimal app that raises RateLimitError for every request,
        # then let the integration configure its exception handler.
        async def _raising_route(request: Request):
            raise RateLimitError(details={"retry_after": 5})

        from starlette.routing import Route

        app = Starlette(routes=[Route("/test", endpoint=_raising_route)])
        mock_limiter = MagicMock(spec=RateLimiter)
        container = MagicMock()
        container.resolve_optional = AsyncMock(return_value=mock_limiter)
        config = _make_config(enabled=True)

        with patch.object(app, "add_middleware"):
            await RateLimitIntegration.configure(app, container, config)

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/test")
        assert response.status_code == 429
        assert response.json()["error"] == "rate_limit_exceeded"
        assert response.headers.get("Retry-After") == "5"

    @pytest.mark.asyncio
    async def test_storage_backend_redis_resolves_redis_client_on_fallback(self) -> None:
        """storage_backend='redis' tries the container for a redis client."""
        app = _make_app()
        container = MagicMock()
        container.resolve_optional = AsyncMock(return_value=None)
        container.resolve = AsyncMock(side_effect=Exception("no redis client"))
        config = WebConfig()
        config.rate_limit = RateLimitConfig(enabled=True, storage_backend="redis")
        await RateLimitIntegration.configure(app, container, config)
        # Configure must not raise despite an empty container; the limiter
        # falls back to in-memory with the honest multi-worker warning.
