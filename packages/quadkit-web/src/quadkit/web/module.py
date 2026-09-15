"""Web module for dependency injection."""

from __future__ import annotations

from typing import Any

from quadkit.contracts.web import WebRateLimiterProtocol
from quadkit.di.module import DynamicModule, Module, module
from quadkit.web.config import ServerConfig, WebConfig  # ServerConfig used in stub()
from quadkit.web.di.provider import WebProvider


@module()
class WebModule(Module):
    """Web module with HTTP provider."""

    @classmethod
    def configure(
        cls,
        controllers: list[type] | None = None,
        discover: list[str] | tuple[str, ...] | None = None,
        host: str | None = None,
        port: int | None = None,
        websocket_handlers: list[type] | None = None,
        **kwargs: Any,
    ) -> DynamicModule:
        """Create a WebModule with explicit configuration.

        Configuration (CORS, CSRF, server host/port, etc.) is loaded from the
        ``[web]`` section of ``application.yaml`` by the orchestrator and injected
        into the provider at registration time.  Pass a ``web_config`` kwarg
        only if you need to bypass YAML entirely.

        Args:
            controllers: Controller classes to register with the web server.
            discover: Package paths to scan for controllers and decorated
                WebSocket handlers, merging them with explicit classes.
            host: Override the server host (builds a ``WebConfig`` internally).
            port: Override the server port (builds a ``WebConfig`` internally).
            **kwargs: Additional keyword arguments forwarded to
                :class:`~quadkit.web.di.provider.WebProvider`.
        """
        resolved_controllers = list(controllers or [])
        resolved_websocket_handlers = list(websocket_handlers or [])
        if discover:
            from quadkit.web.routing.discovery import (
                discover_controllers,
                discover_websocket_handlers,
            )

            for controller in discover_controllers(list(discover)):
                if controller not in resolved_controllers:
                    resolved_controllers.append(controller)
            for handler in discover_websocket_handlers(list(discover)):
                if handler not in resolved_websocket_handlers:
                    resolved_websocket_handlers.append(handler)

        if (host is not None or port is not None) and "web_config" not in kwargs:
            server_kwargs: dict[str, Any] = {}
            if host is not None:
                server_kwargs["host"] = host
            if port is not None:
                server_kwargs["port"] = port
            kwargs["web_config"] = WebConfig(server=ServerConfig(**server_kwargs))

        from quadkit.web.admin.contributor import WebAdminContributor
        from quadkit.web.admin.handlers.active_connections import (
            ActiveConnectionsWidgetHandler,
        )
        from quadkit.web.admin.handlers.request_rate import RequestRateWidgetHandler
        from quadkit.web.admin.handlers.server_status import ServerStatusWidgetHandler

        return DynamicModule(
            module=cls,
            providers=[
                WebProvider(
                    controllers=resolved_controllers,
                    websocket_handlers=resolved_websocket_handlers,
                    **kwargs,
                )
            ],
            is_global=True,
            exports=[
                WebProvider,
                WebRateLimiterProtocol,
                WebAdminContributor,
                ServerStatusWidgetHandler,
                ActiveConnectionsWidgetHandler,
                RequestRateWidgetHandler,
            ],
        )

    @classmethod
    def stub(cls, config: Any = None) -> DynamicModule:
        """Return a no-op WebModule suitable for unit testing.

        Registers WebProvider with no controllers and test-safe
        configuration. No real HTTP server is started.

        Args:
            config: Optional test configuration override.

        Returns:
            A DynamicModule with in-memory web configuration.
        """
        web_config = WebConfig(server=ServerConfig(host="127.0.0.1", port=8000))
        return DynamicModule(
            module=cls,
            providers=[WebProvider(web_config=web_config, controllers=[])],
            is_global=True,
            exports=[WebProvider, WebRateLimiterProtocol],
        )


__all__ = ["WebModule"]
