"""Graceful shutdown management for the web server.

Provides GracefulShutdownManager for connection draining.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Receive, Scope, Send


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
        from starlette.responses import JSONResponse

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
