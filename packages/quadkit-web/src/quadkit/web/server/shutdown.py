"""Graceful shutdown management for the web server.

Provides GracefulShutdownManager for connection draining.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from quadkit.contracts.core.lifecycle import OnBeforeShutdownProtocol
from quadkit.contracts.core.provider import ProviderPriority
from quadkit.di.provider import Provider
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Receive, Scope, Send

    from quadkit.contracts.core.di import (
        ContainerRegistrarProtocol,
        ContainerResolverProtocol,
    )

logger = get_logger(__name__)


class GracefulShutdownManager:
    """Manages graceful shutdown with connection draining."""

    def __init__(self, timeout: float = 30.0):
        self._timeout = timeout
        self._active_connections: int = 0
        self._shutting_down: bool = False
        self._drain_event: asyncio.Event | None = None

    @property
    def is_shutting_down(self) -> bool:
        """Check if shutdown is in progress."""
        return self._shutting_down

    @property
    def active_connections(self) -> int:
        """Get the number of active connections."""
        return self._active_connections

    async def wait_for_drain(self) -> None:
        """Wait for active connections to complete or timeout."""
        if self._drain_event is None:
            self._drain_event = asyncio.Event()

        try:
            await asyncio.wait_for(
                self._drain_event.wait(),
                timeout=self._timeout,
            )
        except TimeoutError:
            # Timeout reached, proceed with shutdown anyway
            pass

    def begin_shutdown(self) -> None:
        """Begin the shutdown process."""
        self._shutting_down = True
        if self._drain_event:
            # If no active connections, signal immediately
            if self._active_connections == 0:
                self._drain_event.set()

    def complete_shutdown(self) -> None:
        """Complete the shutdown process."""
        if self._drain_event:
            self._drain_event.set()

    @asynccontextmanager
    async def track_connection(self) -> Any:
        """Context manager to track active connections."""
        self._active_connections += 1
        try:
            yield
        finally:
            self._active_connections -= 1
            # If shutting down and no more connections, signal
            if self._shutting_down and self._active_connections == 0:
                if self._drain_event:
                    self._drain_event.set()

    async def serve_503_during_drain(self, request: Any) -> Any:
        """Return a 503 response during drain period."""
        from quadkit.web.transport.responses import JSONResponse

        return JSONResponse(
            content={
                "error": "service_unavailable",
                "message": "Server is shutting down",
            },
            status_code=503,
            headers={"Retry-After": str(int(self._timeout))},
        )


class ShutdownMiddleware:
    """Middleware that tracks connections for graceful shutdown."""

    def __init__(self, app: ASGIApp, shutdown_manager: GracefulShutdownManager) -> None:
        self.app = app
        self.manager = shutdown_manager

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # If shutting down, return 503
        if self.manager.is_shutting_down:
            response = await self.manager.serve_503_during_drain(None)
            await response(scope, receive, send)
            return

        # Track the connection
        async with self.manager.track_connection():
            await self.app(scope, receive, send)


class GracefulShutdownProvider(Provider, OnBeforeShutdownProtocol):
    """DI provider that coordinates HTTP request draining on shutdown."""

    name = "shutdown"
    priority = ProviderPriority.INFRASTRUCTURE

    def __init__(
        self,
        timeout: float = 30.0,
        shutdown_manager: GracefulShutdownManager | None = None,
    ) -> None:
        super().__init__()
        self._manager = shutdown_manager or GracefulShutdownManager(timeout=timeout)

    @property
    def manager(self) -> GracefulShutdownManager:
        """Return the shared graceful shutdown manager."""
        return self._manager

    @property
    def middleware(self) -> tuple[type[ShutdownMiddleware], dict[str, Any]]:
        """Return the ASGI middleware tuple backed by the shared manager."""
        return (ShutdownMiddleware, {"shutdown_manager": self._manager})

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        """Register the shared graceful shutdown manager singleton."""
        container.singleton(GracefulShutdownManager, instance=self._manager)

    async def boot(self, container: ContainerResolverProtocol) -> None:  # noqa: ARG002
        """No-op: shutdown wiring is shared through DI and middleware config."""

    async def on_before_shutdown(self, signal: str | None = None) -> None:  # noqa: ARG002
        """Begin HTTP drain and wait for in-flight requests to complete."""
        logger.info(
            "shutdown_drain_started",
            active_connections=self._manager.active_connections,
        )
        self._manager.begin_shutdown()
        if self._manager.active_connections > 0:
            await self._manager.wait_for_drain()
        logger.info("shutdown_drain_completed")

    async def shutdown(self) -> None:
        """No-op: request drain already completed in on_before_shutdown()."""


__all__ = [
    "GracefulShutdownManager",
    "GracefulShutdownProvider",
    "ShutdownMiddleware",
]
