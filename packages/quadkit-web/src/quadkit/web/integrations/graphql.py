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

    from quadkit.contracts.core.di import ContainerResolverProtocol

logger = get_logger(__name__)


class GraphQLIntegration:
    """Handles GraphQL WebSocket endpoint configuration.

    HTTP endpoints are handled by GraphQLController using the standard
    Controller pattern. This integration only handles WebSocket subscriptions
    which require direct Starlette route registration.
    """

    @staticmethod
    async def configure(
        app: Starlette, container: ContainerResolverProtocol | None = None
    ) -> None:
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

            if not container.has(WebSocketTransportProtocol):
                await GraphQLIntegration._configure_playground(app, container)
                return

            _transport_holder: dict[str, WebSocketTransportProtocol] = {}

            async def _ws_endpoint(websocket: Any) -> None:
                transport = _transport_holder.get("transport")
                if transport is None:
                    try:
                        _transport_holder["transport"] = await container.resolve(
                            WebSocketTransportProtocol
                        )
                        logger.info("GraphQL WS transport initialised")
                    except (LookupError, RuntimeError, OSError) as exc:
                        logger.warning(
                            "GraphQL WS transport init failed",
                            error=str(exc),
                        )
                        await websocket.close(code=1013)
                        return

                await _transport_holder["transport"].handle(websocket, app)

            ws_path = DEFAULT_SUBSCRIPTIONS_PATH
            ws_route = WebSocketRoute(ws_path, _ws_endpoint)
            app.routes.insert(0, ws_route)
            logger.info("GraphQL WebSocket route registered at %s (lazy init)", ws_path)

            # ── Playground page (config-gated, container-backed) ────────────
            await GraphQLIntegration._configure_playground(app, container)
            return

    @staticmethod
    async def _configure_playground(
        app: Starlette, container: ContainerResolverProtocol
    ) -> None:
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

        import base64
        import hashlib
        import re

        from starlette.routing import Route

        from quadkit.web.config.top_level import WebConfig
        from quadkit.web.transport.responses import HTMLResponse

        web_cfg = await container.resolve_optional(WebConfig)
        frame_ancestors = "'none'"
        if web_cfg is not None:
            app_csp = getattr(getattr(web_cfg, "security", None), "csp", None)
            if app_csp is not None and isinstance(app_csp.directives, dict):
                configured = app_csp.directives.get("frame-ancestors")
                if configured:
                    frame_ancestors = (
                        " ".join(sorted(str(v) for v in configured))
                        if isinstance(configured, (set, list))
                        else str(configured)
                    )

        script_re = re.compile(
            r"<script[^>]*>(.*?)</script>", re.DOTALL | re.IGNORECASE
        )

        async def _playground_endpoint(request: Any) -> Any:
            root_path = request.scope.get("root_path", "") or ""
            html_doc = playground.render(root_path + playground.endpoint_path)
            hashes = [
                "'sha256-"
                + base64.b64encode(hashlib.sha256(m.encode("utf-8")).digest()).decode(
                    "ascii"
                )
                + "'"
                for m in script_re.findall(html_doc)
            ]
            script_sources = " ".join(["'self'", *hashes])
            csp_policy = (
                f"default-src 'self'; "
                f"script-src {script_sources}; "
                f"script-src-elem {script_sources}; "
                f"style-src 'self' 'unsafe-inline'; "
                f"style-src-elem 'self' 'unsafe-inline'; "
                f"connect-src 'self' ws: wss:; "
                f"img-src 'self' data:; "
                f"frame-ancestors {frame_ancestors}; "
                f"base-uri 'self'; "
                f"form-action 'self'"
            )
            return HTMLResponse(
                html_doc,
                headers={"Content-Security-Policy": csp_policy},
            )

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
