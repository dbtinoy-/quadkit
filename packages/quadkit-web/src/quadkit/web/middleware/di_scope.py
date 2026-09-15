"""DI Scope Middleware for request-scoped dependency injection.

Ensures DI container is properly scoped per request to prevent
data leaks and memory issues.

This middleware:
1. Creates a child container for each request
2. Attaches it to request.state.container
3. Properly disposes of scoped resources after the request
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast
import uuid

from starlette.requests import Request

from quadkit.logging import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Receive, Scope, Send

    from quadkit.di.container import Container


class DIScopeMiddleware:
    """
    Pure ASGI middleware that creates a request-scoped DI container.

    Creates a child container for each request to ensure proper
    isolation of request-scoped services (like UnitOfWork, RequestContext).
    """

    def __init__(
        self,
        app: ASGIApp,
        container: Container | None = None,
        scoped_services: list[type] | None = None,
    ):
        """
        Initialize the DI scope middleware.

        Args:
            app: The ASGI application
            container: The root DI container
            scoped_services: Optional list of service types to register as scoped
        """
        self.app = app
        self.container = container
        self.scoped_services = scoped_services or []

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Pure ASGI middleware implementation - no task creation overhead."""

        if scope["type"] != "http":
            # Pass through non-HTTP requests (WebSocket, lifespan, etc.)
            await self.app(scope, receive, send)
            return

        # Extract request info from ASGI scope
        headers = dict(scope.get("headers", []))
        request_id = headers.get(b"x-request-id", str(uuid.uuid4()).encode()).decode()

        # Create request-scoped container
        request_container: Any = None
        service_scope: Any = None
        if self.container is not None:
            try:
                # Create a scope for this request using create_scope()
                if hasattr(self.container, "create_scope"):
                    service_scope = self.container.create_scope()
                    request_container = service_scope
                elif hasattr(self.container, "child"):
                    # Fallback to child() if create_scope() not available
                    request_container = self.container.child()
                else:
                    raise RuntimeError(
                        "Container has no create_scope() or child() method — cannot create request scope"
                    )

                # Register scoped services in the scoped container
                for service_type in self.scoped_services:
                    if hasattr(request_container, "register_scoped"):
                        request_container.register_scoped(service_type, service_type)
                    elif hasattr(request_container, "scoped"):
                        request_container.scoped(service_type)
            except (RuntimeError, LookupError) as exc:
                logger.error("di_scope_creation_failed", error=str(exc))
                raise RuntimeError("Failed to create request scope") from exc

        try:
            # Create a minimal Request object for DI scope
            request = Request(scope, receive)

            # Attach scoped container and request to request state
            request.state.container = request_container
            request.state.root_container = self.container
            request.state.request_id = request_id

            # Use service_scope for disposal check later

            # Also make available via the container if possible
            if request_container is not None and hasattr(
                request_container,
                "__setitem__",
            ):
                request_container["request"] = request
                request_container["request_id"] = request_id

            # Process request with scoped container
            await self.app(scope, receive, send)
        finally:
            # Scope cleanup MUST run even when the app raises: otherwise
            # request-scoped resources (database sessions, connections)
            # leak on every errored request. Context vars are managed
            # by RequestContextMiddleware.
            if service_scope is not None and hasattr(service_scope, "dispose"):
                try:
                    await cast("Any", service_scope).dispose()
                except Exception as exc:  # noqa: BLE001 — best-effort cleanup must never mask the request outcome
                    logger.warning("scope_dispose_failed", error=str(exc))
            elif request_container is not None and hasattr(
                request_container,
                "dispose",
            ):
                try:
                    await cast("Any", request_container).dispose()
                except Exception as exc:  # noqa: BLE001 — best-effort cleanup must never mask the request outcome
                    logger.warning("container_dispose_failed", error=str(exc))


__all__ = ["DIScopeMiddleware"]
