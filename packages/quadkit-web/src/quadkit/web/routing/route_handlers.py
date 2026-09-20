"""Registry for route handlers in quadkit-web."""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any, Protocol, cast

from quadkit.logging import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from collections.abc import Callable

    from quadkit.app.base import Application
    from quadkit.web.routing.manager import WebRouterManager


class RouteHandlerProtocol(Protocol):
    """Protocol for route handlers."""

    async def register(self, manager: WebRouterManager, app: Application) -> None:
        """Register routes into the application."""
        ...


def _is_body_model(annotation: type) -> bool:
    """Return True if *annotation* is a Pydantic BaseModel or DomainModel subclass.

    Both types can be deserialised from a JSON request body.  Imported lazily
    to avoid circular-dependency issues at module load time.

    Args:
        annotation: The type annotation to test.

    Returns:
        True when the annotation is a recognised model type.
    """
    try:
        from pydantic import BaseModel

        if issubclass(annotation, BaseModel):
            return True
    except ImportError:
        pass
    try:
        from quadkit.domain import DomainModel

        if issubclass(annotation, DomainModel):
            return True
    except ImportError:
        pass
    return False


def _wrap_script_handler(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Wrap a script-mode standalone handler to be Starlette-compatible.

    Handles parameter binding:
    - Path params: matched by name from ``request.path_params``
    - Body param: ``data: dict`` / Pydantic ``BaseModel`` / ``DomainModel`` subclass
      (or any unhinted param) ← parsed from JSON body
    - ``request``: passes the raw Starlette ``Request`` object
    Return values: dict/list → JSONResponse, None → 204, (body, status) tuple
    """
    from starlette.requests import Request
    from starlette.responses import JSONResponse, Response

    sig = inspect.signature(fn)
    params = list(sig.parameters.values())

    async def endpoint(request: Request) -> Response:
        kwargs: dict[str, Any] = {}

        # Parse JSON body once (only for methods that carry a body)
        body: dict | list | None = None
        if request.method in ("POST", "PUT", "PATCH"):
            try:
                body = await request.json()
            except (ValueError, UnicodeDecodeError):
                body = None

        for param in params:
            name = param.name
            annotation = param.annotation

            if annotation is inspect.Parameter.empty:
                # Unnamed hint: treat as body if body available, else skip
                if body is not None:
                    kwargs[name] = body
            elif annotation is Request or (
                isinstance(annotation, type) and issubclass(annotation, Request)
            ):
                kwargs[name] = request
            elif name in request.path_params:
                kwargs[name] = request.path_params[name]
            elif annotation is dict or (
                isinstance(annotation, type) and issubclass(annotation, dict)
            ):
                kwargs[name] = body or {}
            elif isinstance(annotation, type) and _is_body_model(annotation):
                body_dict: dict[str, Any] = body if isinstance(body, dict) else {}
                try:
                    from pydantic import BaseModel, ValidationError

                    if issubclass(annotation, BaseModel):
                        try:
                            kwargs[name] = annotation(**body_dict)
                        except ValidationError as exc:
                            return JSONResponse(
                                {"errors": exc.errors()}, status_code=422
                            )
                    else:
                        try:
                            kwargs[name] = annotation(**body_dict)
                        except Exception:  # noqa: BLE001 — a non-model type that cannot be built from the body is a client error, not a 500
                            return JSONResponse(
                                {"errors": [{"loc": [name], "msg": "invalid body"}]},
                                status_code=422,
                            )
                except ImportError:
                    kwargs[name] = body_dict
            elif name in request.query_params:
                raw = request.query_params[name]
                # Best-effort type coercion for query params
                if annotation in (int,):
                    try:
                        kwargs[name] = int(raw)
                    except ValueError:
                        kwargs[name] = raw
                elif annotation in (float,):
                    try:
                        kwargs[name] = float(raw)
                    except ValueError:
                        kwargs[name] = raw
                elif annotation in (bool,):
                    kwargs[name] = raw.lower() in ("1", "true", "yes")
                else:
                    kwargs[name] = raw
            elif isinstance(annotation, type) and not annotation.__module__.startswith(
                "builtins"
            ):
                # Try to resolve arbitrary service from DI container (script-mode DI injection)
                try:
                    from quadkit.contracts.exceptions.container import (
                        UnresolvableDependencyError,
                    )

                    container = getattr(
                        getattr(request.app, "state", None), "container", None
                    )
                    if container is not None:
                        kwargs[name] = await container.resolve(annotation)
                except (UnresolvableDependencyError, AttributeError, LookupError):
                    pass
            elif param.default is not inspect.Parameter.empty:
                # Optional param with default — skip (let Python fill default)
                pass

        result = await fn(**kwargs)

        # Tuple (body, status_code)
        if isinstance(result, tuple) and len(result) == 2:
            body_out, status = result
            if isinstance(body_out, Response):
                return body_out
            return JSONResponse(body_out, status_code=int(status))

        if result is None:
            return Response(status_code=204)
        if isinstance(result, Response):
            return result
        return JSONResponse(result)

    return endpoint


def _wrap_websocket_handler(handler_cls: type) -> Callable:
    """Wrap a AbstractWebSocketHandler class to be Starlette/ASGI compatible.

    Resolves the handler instance from the DI container (preferring singletons
    for broadcast support) and dispatches the connection to his ``handle()``
    method.
    """

    from quadkit.contracts.exceptions.container import UnresolvableDependencyError
    from quadkit.web.transport.websockets import WebSocket

    async def endpoint(starlette_ws: Any) -> None:
        # Resolve handler from container if available
        container = None
        if hasattr(starlette_ws, "app"):
            container = getattr(
                getattr(starlette_ws.app, "state", None), "container", None
            )

        handler: Any = None
        if container is not None:
            try:
                # Try to resolve from container (preferred for singleton/lifecycle)
                handler = await container.resolve(handler_cls)
            except (LookupError, RuntimeError, UnresolvableDependencyError):
                # Fallback to direct instantiation if not injectable. Other
                # configuration and visibility failures remain fail-closed.
                handler = handler_cls()
        else:
            handler = handler_cls()

        # Wrap Starlette WebSocket in Quadkit WebSocket
        ws = WebSocket(starlette_ws)

        # Dispatch to Quadkit handler
        await handler.handle(ws)

    return endpoint


class CoreRouteHandler:
    """Handles core routes from application decorators."""

    async def register(self, manager: WebRouterManager, app: Application) -> None:
        starlette = manager.provider.starlette
        if starlette is None:
            raise RuntimeError("Starlette application not initialized")

        # `app` here is the Starlette instance. Resolve the Quadkit Application
        # from the container to access script-mode _pending_routes.
        qk_app: Any = app
        try:
            from quadkit.app.base import Application as QuadkitApp
            from quadkit.contracts.exceptions.container import (
                UnresolvableDependencyError,
            )

            starlette_app = manager.provider.starlette
            container = getattr(starlette_app, "state", None)
            container = getattr(container, "container", None) if container else None
            if container is not None:
                resolved = await container.resolve(
                    QuadkitApp,
                    bypass_visibility=True,
                )
                if resolved is not None:
                    qk_app = resolved
        except (
            LookupError,
            RuntimeError,
            AttributeError,
            TypeError,
            UnresolvableDependencyError,
        ) as _exc:
            logger.debug("quickstart_app_resolution_skipped", reason=str(_exc))

        pending = getattr(qk_app, "_pending_routes", [])
        if not isinstance(pending, (list, tuple)):
            pending = []

        if not pending:
            return

        logger.info("Registering %d core routes from application", len(pending))

        for route_def in pending:
            # WEBSOCKET routes should be wrapped using _wrap_websocket_handler
            # to bridge the ASGI interface (REVISION COR-1)
            if route_def.method == "WEBSOCKET":
                use_handler = _wrap_websocket_handler(route_def.handler)
            else:
                use_handler = _wrap_script_handler(route_def.handler)

            await manager.add_route(
                path=str(route_def.path),
                handler=use_handler,
                method=str(route_def.method),
                origin_type="core",
                handler_metadata=route_def.handler,
            )

        # Consume pending routes to prevent double registration (REVISION MAJ-6)
        if hasattr(qk_app, "_pending_routes"):
            qk_app._pending_routes = []


class ControllerRouteHandler:
    """Handles controller-based routes.

    Discovers controllers from two sources and merges them:
    1. Controllers registered directly on the ``WebProvider`` instance.
    2. Controllers declared in the ``controllers=`` field of any ``@module``
       decorated class that is registered with the Application container.
    """

    async def register(self, manager: WebRouterManager, app: Application) -> None:
        # Start with directly-registered controllers
        seen: set[type] = set()
        controllers_to_register: list[type] = []

        for ctrl in manager.provider.controllers:
            if ctrl not in seen:
                seen.add(ctrl)
                controllers_to_register.append(ctrl)

        # Auto-discover controllers from @module-decorated classes
        try:
            from quadkit.di.module import Module as QuadkitModule

            if hasattr(app, "container") and app.container is not None:
                # Iterate all registered singletons — find module metadata owners
                # Use the registry to discover all registered classes
                container = cast("Any", app.container)
                for descriptor in list(container._registry.all()):
                    registered_cls = descriptor.service_type
                    meta = getattr(registered_cls, "__quadkit_module__", None)
                    if meta is not None and isinstance(meta, QuadkitModule):
                        for ctrl_cls in meta.controllers:
                            if ctrl_cls not in seen:
                                seen.add(ctrl_cls)
                                controllers_to_register.append(ctrl_cls)
                                logger.debug(
                                    "auto_discovered_controller_from_module",
                                    controller=ctrl_cls.__name__,
                                    module=meta.name,
                                )
        except (
            ImportError,
            AttributeError,
            LookupError,
            RuntimeError,
            TypeError,
        ) as exc:
            logger.debug("module_controller_discovery_skipped", reason=str(exc))

        for controller_cls in controllers_to_register:
            await manager.register_controller_routes(controller_cls, app.container)


class WebSocketRouteHandler:
    """Register explicitly discovered ``@websocket_handler`` classes."""

    async def register(self, manager: WebRouterManager, _app: Application) -> None:
        """Mount each configured WebSocket handler as a Starlette route."""
        websocket_handlers = getattr(manager.provider, "websocket_handlers", [])
        for handler_cls in websocket_handlers:
            path = getattr(handler_cls, "_ws_path", None)
            if not isinstance(path, str) or not path:
                logger.warning(
                    "websocket_handler_missing_path",
                    handler=getattr(handler_cls, "__name__", repr(handler_cls)),
                )
                continue

            await manager.add_route(
                path=path,
                handler=_wrap_websocket_handler(handler_cls),
                method="WEBSOCKET",
                origin_type="websocket",
                handler_metadata=handler_cls,
            )


class OpenAPIRouteHandler:
    """Handles OpenAPI documentation routes."""

    async def register(self, manager: WebRouterManager, _app: Application) -> None:
        web_config = manager.provider.web_config
        openapi_title = web_config.openapi_title

        if openapi_title and manager.provider.openapi_generator:
            from quadkit.web.routing.openapi import (
                register_openapi_routes,
            )

            register_openapi_routes(manager.provider)  # type: ignore[arg-type]


class HealthRouteHandler:
    """Handles health check routes."""

    async def register(self, manager: WebRouterManager, app: Application) -> None:
        from quadkit.web.routing.health import register_health_route

        register_health_route(manager.provider, app)  # type: ignore[arg-type]


class DebugRouteHandler:
    """Handles debug routes when enabled."""

    async def register(self, manager: WebRouterManager, _app: Application) -> None:
        if manager.should_enable_debug_routes():
            from quadkit.web.routing.debug import (
                register_debug_routes,
            )

            register_debug_routes(manager.provider)  # type: ignore[arg-type]


class RouteHandlerRegistry:
    """Registry for route source handlers.

    Each handler (core routes, controllers, WebSockets, OpenAPI, health,
    debug) knows how to discover and register its routes with the router manager.
    """

    def __init__(self) -> None:
        self._handlers: list[RouteHandlerProtocol] = [
            CoreRouteHandler(),
            ControllerRouteHandler(),
            WebSocketRouteHandler(),
            OpenAPIRouteHandler(),
            HealthRouteHandler(),
            DebugRouteHandler(),
        ]

    def add_handler(self, handler: RouteHandlerProtocol) -> None:
        """Add a custom route source handler.

        **Public Extension Point** — use this to inject custom route discovery
        logic without subclassing ``WebProvider``.  Custom handlers run after
        all built-in handlers, so they can reference routes registered by the
        framework.

        Register via the provider::

            class MyRouteHandler:
                async def register_routes(self, router_manager, container):
                    router_manager.add_route("/my/path", my_view, methods=["GET"])

            class AppProvider(WebProvider):
                async def boot(self, container):
                    await super().boot(container)
                    route_handler_registry = await container.resolve(RouteHandlerRegistry)
                    route_handler_registry.add_handler(MyRouteHandler())

        Args:
            handler: A :class:`RouteHandlerProtocol` implementation.
        """
        self._handlers.append(handler)

    @property
    def handlers(self) -> list[RouteHandlerProtocol]:
        """Get all registered handlers."""
        return self._handlers
