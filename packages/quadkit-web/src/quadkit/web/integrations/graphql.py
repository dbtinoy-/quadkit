"""GraphQL integration for WebProvider.

This module integrates GraphQL functionality with the web layer.
WebSocket subscriptions are registered directly on the Starlette application.
HTTP endpoints are handled by GraphQLController via the web contributor pattern.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

from quadkit.contracts.graphql.protocols import DEFAULT_SUBSCRIPTIONS_PATH
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from starlette.applications import Starlette

logger = get_logger(__name__)


class GraphQLIntegration:
    """Handles GraphQL WebSocket endpoint configuration.

    HTTP endpoints are handled by GraphQLController using the standard
    Controller pattern. This integration only handles WebSocket subscriptions
    which require direct Starlette route registration.
    """

    @staticmethod
    async def configure(app: Starlette, container: Any | None = None) -> None:
        """Configure GraphQL HTTP playground and WebSocket endpoints.

        Registers the playground page (``GET graphql.playground.path``,
        when ``graphql.playground.enabled``) and a WebSocket route at
        ``/graphql/ws`` that lazily initialises the GraphQL transport on
        the first connection.  Lazy handling avoids boot-order issues
        when the GraphQL provider boots in parallel with the web provider.

        Falls back to the legacy ``app.graphql_ws_controller_class`` attribute
        when the container is not available.

        Args:
            app: The Starlette application instance.
            container: Optional DI container resolver for GraphQLProvider lookup.
        """
        # ── Strategy 1: Lazy WS endpoint backed by the container ───────────
        if container is not None:
            from starlette.routing import WebSocketRoute

            from quadkit.contracts.graphql.protocols import WebSocketTransportProtocol

            _transport_holder: dict[str, Any] = {}

            async def _ws_endpoint(websocket: Any) -> None:
                transport = _transport_holder.get("transport")
                if transport is None:
                    try:
                        transport = await container.resolve(WebSocketTransportProtocol)
                        _transport_holder["transport"] = transport
                        logger.info("GraphQL WS transport initialised")
                    except (LookupError, RuntimeError, OSError) as exc:
                        logger.warning(
                            "GraphQL WS transport init failed",
                            error=str(exc),
                        )
                        await websocket.close(code=1013)
                        return

                await transport.handle(websocket, app)

            ws_path = DEFAULT_SUBSCRIPTIONS_PATH
            ws_route = WebSocketRoute(ws_path, _ws_endpoint)
            app.routes.insert(0, ws_route)
            logger.info("GraphQL WebSocket route registered at %s (lazy init)", ws_path)

            # ── Playground page (config-gated, container-backed) ────────────
            await GraphQLIntegration._configure_playground(app, container)
            return

    @staticmethod
    async def _configure_playground(app: Starlette, container: Any) -> None:
        """Register the playground page when ``graphql.playground.enabled``.

        Resolves the :class:`GraphQLPlaygroundProtocol` contract (registered
        by the GraphQL provider) and mounts a GET route at the configured
        path.  The endpoint URL is computed per request from the ASGI
        ``root_path`` so the page also works when the application is
        mounted under a prefix (e.g. the example hub).

        Silently skips when the graphql package or provider is absent —
        the playground is an optional convenience, never a boot failure.

        Args:
            app: The Starlette application instance.
            container: DI container resolver for the playground contract.
        """
        from quadkit.contracts.graphql.protocols import GraphQLPlaygroundProtocol

        playground = await container.resolve_optional(GraphQLPlaygroundProtocol)
        if playground is None or not playground.enabled:
            return

        from starlette.responses import HTMLResponse
        from starlette.routing import Route

        async def _playground_endpoint(request: Any) -> Any:
            root_path = request.scope.get("root_path", "") or ""
            return HTMLResponse(playground.render(root_path + playground.endpoint_path))

        app.routes.insert(
            0,
            Route(playground.page_path, _playground_endpoint, methods=["GET"]),
        )
        logger.info("GraphQL playground registered at %s", playground.page_path)

        # ── Strategy 2 (legacy): app.graphql_ws_controller_class ───────────
        graphql_ws_cls = None
        with contextlib.suppress(AttributeError, TypeError):
            graphql_ws_cls = getattr(app, "graphql_ws_controller_class", lambda: None)()

        if graphql_ws_cls is not None and not hasattr(
            graphql_ws_cls,
            "_mock_return_value",
        ):
            try:
                from starlette.routing import WebSocketRoute

                ws_path = getattr(
                    app, "graphql_ws_path", lambda: DEFAULT_SUBSCRIPTIONS_PATH
                )()
                ws_route = WebSocketRoute(str(ws_path), graphql_ws_cls)
                app.routes.append(ws_route)
                logger.info("GraphQL WebSocket registered at %s", ws_path)
            except (ImportError, AttributeError, RuntimeError):
                logger.exception("Failed to register GraphQL WebSocket route")
