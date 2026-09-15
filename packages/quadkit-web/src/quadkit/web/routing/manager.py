"""Router manager for quadkit-web."""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any, cast

from quadkit.logging import get_logger
from quadkit.web.protocols import WebProviderProtocol

if TYPE_CHECKING:
    from quadkit.contracts.core.di import ContainerResolverProtocol
    from quadkit.web.routing.controllers import Controller

logger = get_logger(__name__)


class WebRouterManager:
    """Manages route registration, controller discovery, and OpenAPI generation."""

    def __init__(self, provider: WebProviderProtocol):
        self.provider = provider
        self._registered_routes: dict[tuple[str, str], list[dict]] = {}
        from quadkit.web.routing.route_handlers import (
            RouteHandlerRegistry,
        )

        self._route_registry = RouteHandlerRegistry()

    def add_handler(self, handler: Any) -> None:
        """Add a custom route handler to the registry."""
        self._route_registry.add_handler(handler)

    def _format_route_origin(self, origin: dict) -> str:
        parts = []
        t = origin.get("type")
        if t == "core":
            parts.append(f"handler={origin.get('handler_name')}")
        elif t == "controller":
            parts.append(f"controller={origin.get('controller')}")
            parts.append(f"handler={origin.get('handler_name')}")
        module = origin.get("module")
        if module:
            parts.append(f"module={module}")
        file = origin.get("file")
        if file:
            parts.append(f"file={file}")
        line = origin.get("line")
        if line:
            parts.append(f"line={line}")
        return ", ".join(parts)

    async def register_routes(
        self, app: Any, container: ContainerResolverProtocol
    ) -> Any:
        """Discovers and registers all routes using the registry and modules."""
        logger.info("Initializing web route discovery...")

        # 1. Run custom route handlers (e.g. CoreRouteHandler, ControllerRouteHandler)

        # 3. Run custom route handlers (e.g. legacy @route decorator handlers)
        for handler in self._route_registry.handlers:
            handler_name = type(handler).__name__
            logger.debug("Running route discovery for %s", handler_name)
            await handler.register(self, app)

        route_count = len(self._registered_routes)
        logger.info("Route registration complete. Total routes: %s", route_count)

    def should_enable_debug_routes(self) -> bool:
        cfg = self.provider.web_config
        p_cfg = self.provider.provider_config
        return (
            getattr(cfg, "debug_routes", False)
            or getattr(p_cfg, "debug_routes", False)
            or self.provider.debug_routes_auth is not None
            or getattr(cfg, "debug_routes_token", None) is not None
            or getattr(p_cfg, "debug_routes_token", None) is not None
            or getattr(cfg, "debug_routes_rate_limit", 0) > 0
            or getattr(p_cfg, "debug_routes_rate_limit", 0) > 0
            or getattr(self.provider, "_debug_routes_redis_client_arg", None)
            is not None
        )

    async def add_route(
        self,
        path: str,
        handler: Any,
        method: str,
        origin_type: str,
        handler_metadata: Any = None,
        controller_cls: type | None = None,
        route_meta: dict[str, Any] | None = None,
    ) -> None:
        """Centralized route registration with duplicate detection."""
        path = str(path)
        method = str(method).upper()

        starlette = self.provider.starlette
        if starlette is None:
            raise RuntimeError("Starlette application not initialized")

        key = (method, path)
        origin: dict[str, Any] = {"type": origin_type}

        if origin_type == "core" and handler_metadata:
            origin["handler_name"] = str(
                getattr(
                    handler_metadata,
                    "__name__",
                    repr(handler_metadata),
                ),
            )
            origin["module"] = getattr(handler_metadata, "__module__", None)
            try:
                code = getattr(handler_metadata, "__code__", None)
                if code is not None:
                    origin["file"] = getattr(code, "co_filename", None)
                    origin["line"] = getattr(code, "co_firstlineno", None)
            except (AttributeError, TypeError):
                pass
        elif origin_type == "controller" and controller_cls:
            origin["controller"] = controller_cls.__name__
            origin["handler_name"] = (
                handler_metadata if isinstance(handler_metadata, str) else "unknown"
            )
            origin["module"] = controller_cls.__module__
            try:
                func = getattr(controller_cls, origin["handler_name"], None)
                if func:
                    source_file = inspect.getsourcefile(func)
                    if source_file:
                        origin["file"] = source_file
                    code = getattr(func, "__code__", None)
                    if code:
                        origin["line"] = getattr(code, "co_firstlineno", None)
            except (OSError, TypeError, AttributeError):
                pass

        if key in self._registered_routes:
            existing = self._registered_routes[key][0]
            msg = (
                f"Duplicate route registration detected: {method} {path}\n"
                f"Existing: {self._format_route_origin(existing)}\n"
                f"New: {self._format_route_origin(origin)}"
            )
            if self.provider.fail_on_route_conflict:
                raise RuntimeError(msg)
            logger.warning(msg)
            return

        self._registered_routes[key] = [origin]
        if method == "WEBSOCKET":
            from starlette.routing import WebSocketRoute

            starlette.router.routes.append(WebSocketRoute(path, handler))
        else:
            starlette.add_route(path, handler, methods=[method])

        # Store Quadkit Route metadata if supported
        if hasattr(self.provider.router, "add_route"):
            original_handler = handler
            if (
                origin_type == "controller"
                and controller_cls
                and isinstance(handler_metadata, str)
            ):
                original_handler = getattr(controller_cls, handler_metadata, handler)

            meta_kwargs = route_meta or {}
            name = meta_kwargs.pop("name", None)
            meta_kwargs.pop("method", None)
            meta_kwargs.pop("path", None)

            self.provider.router.add_route(
                method=method,
                path=path,
                handler=original_handler,
                name=name,
                controller_cls=controller_cls,
                **meta_kwargs,
            )

        logger.debug("Registered route: %s %s (origin: %s)", method, path, origin_type)

    async def register_controller_routes(
        self,
        controller_cls: type[Controller],
        container: ContainerResolverProtocol,
    ) -> None:
        """Registers routes for a specific controller.

        Uses collect_routes() if available (recommended), otherwise falls back
        to _routes attribute (legacy metaclass-based approach).
        """
        # Mirror the controller into the global route registry so admin
        # pages and tooling can discover the routes actually being mounted.
        from quadkit.web.routing import register_controller

        register_controller(controller_cls)

        # Collect routes from controller
        routes = controller_cls.collect_routes()

        prefix = getattr(controller_cls, "prefix", "")

        for route_meta in routes:
            raw_path = str(
                route_meta.get("path")
                if isinstance(route_meta, dict)
                else getattr(route_meta, "path", None),
            )
            method = str(
                route_meta.get("method", "GET").upper()
                if isinstance(route_meta, dict)
                else getattr(route_meta, "method", "GET").upper(),
            )

            # WebSocket controller methods are mounted as WebSocketRoute and
            # receive a Starlette WebSocket — the HTTP request pipeline cannot
            # serve them, so they get a dedicated endpoint factory.
            factory_name = (
                "_create_websocket_endpoint"
                if method == "WEBSOCKET"
                else "_create_endpoint"
            )
            create_endpoint = getattr(self.provider.router, factory_name, None)
            if create_endpoint is None:
                msg = f"Router missing internal endpoint creator ({factory_name})"
                raise RuntimeError(msg)

            handler = create_endpoint(
                controller_cls,
                route_meta["handler_name"],
                container,
            )
            full_path = (
                raw_path
                if raw_path.startswith(prefix)
                else prefix.rstrip("/") + raw_path
            )
            if not full_path.startswith("/"):
                full_path = "/" + full_path

            await self.add_route(
                path=full_path,
                handler=handler,
                method=method,
                origin_type="controller",
                handler_metadata=str(route_meta.get("handler_name", "unknown")),
                controller_cls=controller_cls,
                route_meta=route_meta,
            )

    def generate_openapi_spec(self) -> dict[str, Any]:
        """Generates OpenAPI specification."""
        if not self.provider.openapi_generator:
            return {}
        return cast(
            "dict[str, Any]",
            self.provider.openapi_generator.generate_spec(self.provider.controllers),
        )
