"""Convention followed: **Composition root** — one file knows how modules,
providers, handlers and controllers fit; ``create_app(config=...)`` is the
injection seam.

Composition root for the WebSocket Echo demo: one ``@websocket_handler``
class lifecycle (connect, message, disconnect), JSON messages,
per-connection state, and a stats facet over the same room registry the
sockets use.
"""

from __future__ import annotations

from quadkit.app.base import Application
from quadkit.config.main import QuadkitConfig
from quadkit.di.provider import Provider
from quadkit.web.module import WebModule
from websocket_echo.controllers.api import StatsController
from websocket_echo.di.provider import WebSocketEchoProvider
from websocket_echo.handlers.echo import EchoHandler


def build_modules() -> list[object]:
    """Build the Quadkit modules required by the WebSocket Echo demo."""
    return [
        WebModule.configure(
            controllers=[StatsController], websocket_handlers=[EchoHandler]
        )
    ]


def build_providers() -> list[Provider]:
    """Build the DI providers for the WebSocket Echo demo."""
    return [WebSocketEchoProvider()]


def create_app(config: QuadkitConfig | None = None) -> Application:
    """Create and configure the WebSocket Echo application."""
    app = Application(name="websocket-echo", config=config)
    app.add_modules(build_modules())
    app.add_providers(build_providers())
    return app


__all__ = ["build_modules", "build_providers", "create_app"]
