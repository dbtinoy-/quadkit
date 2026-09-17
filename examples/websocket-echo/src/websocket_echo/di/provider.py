"""Convention followed: **Provider lifecycle** — ``register()`` declares
singletons (including the controller, as a class binding), ``boot()``
builds the wired controller instance and rebinds it, ``shutdown()``
releases resources, ``health_check()`` reports readiness;
``config_key``/``config_model`` wire the typed yaml section into
``self.config``.

Lifecycle wiring for the WebSocket Echo demo: the room registry is the
shared state between the socket handler and the stats controller, so the
provider owns it — handler class attribute plus container singleton.
"""

from __future__ import annotations

from quadkit.contracts.core import HealthCheckResult, HealthStatus
from quadkit.contracts.core.di import (
    ContainerRegistrarProtocol,
    ContainerResolverProtocol,
)
from quadkit.di.provider import Provider
from websocket_echo.config import WebSocketEchoConfig
from websocket_echo.controllers.api import StatsController
from websocket_echo.handlers.echo import EchoHandler
from websocket_echo.services.rooms import ConnectionRegistry


class WebSocketEchoProvider(Provider):
    """Own the room registry and the controller wiring."""

    name = "websocket_echo"
    config_key: str | None = "websocket_echo"
    config_model: type | None = WebSocketEchoConfig

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        config = (
            self.config
            if isinstance(self.config, WebSocketEchoConfig)
            else WebSocketEchoConfig()
        )
        registry = ConnectionRegistry(max_room_members=config.max_room_members)
        container.singleton(ConnectionRegistry, instance=registry)
        EchoHandler.registry = registry  # handler instances share the class
        container.singleton(StatsController, StatsController)

    async def boot(self, container: ContainerResolverProtocol) -> None:
        registry = await container.resolve(ConnectionRegistry)
        container.bind(StatsController, StatsController(registry))

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Report provider wiring for framework health aggregation."""
        config = (
            self.config
            if isinstance(self.config, WebSocketEchoConfig)
            else WebSocketEchoConfig()
        )
        return HealthCheckResult(
            component=self.name,
            status=HealthStatus.HEALTHY,
            details={
                "demo": "websocket-echo",
                "max_room_members": config.max_room_members,
            },
        )


__all__ = ["WebSocketEchoProvider"]
