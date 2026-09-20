"""DI Scope Middleware for request-scoped dependency injection.

Ensures DI container is properly scoped per request to prevent
data leaks and memory issues.

This middleware:
1. Creates a child container for each request
2. Attaches it to the request state (``request.state.container``)
3. Properly disposes of scoped resources after the request
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast
import uuid

from quadkit.logging import get_logger
from quadkit.web.middleware._headers import get_header, sanitize_request_id

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
        """Initialize the DI scope middleware.

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

        # One request identity per request: an outer middleware (the
        # request-context layer) resolves the id exactly once and stores it
        # in the shared ASGI state. Reuse it instead of minting a second,
        # differently-formatted id; the fallbacks below only run when this
        # middleware is mounted standalone (e.g. without request context).
        state = scope.setdefault("state", {})
        request_id = state.get("request_id")
        if not request_id:
            inbound = get_header(scope, b"x-request-id")
            request_id = sanitize_request_id(
                inbound.decode("ascii", "replace") if inbound is not None else None
            )
            if not request_id:
                request_id = f"req_{uuid.uuid4().hex[:12]}"
            state["request_id"] = request_id

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
            # Attach the scoped container to the shared ASGI state. Starlette's
            # ``Request`` exposes the very same dict as ``request.state``, so
            # handlers and inner middleware read these entries without this
            # middleware having to construct a Request wrapper of its own.
            state["container"] = request_container
            state["root_container"] = self.container

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
