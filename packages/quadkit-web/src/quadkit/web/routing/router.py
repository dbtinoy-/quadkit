"""Router with Controller DI Strategy.

The Router provides declarative routing for controllers with automatic
dependency injection. Routes are defined using decorators on controller
methods, and the router handles request parsing, DI resolution, and
response formatting.

Example:
    Defining routes with a controller::

        from quadkit.web import Controller, get, post

        class UserController(Controller):
            @get("/users")
            async def list_users(self, limit: int = 20) -> list[User]:
                return await self.user_repo.list(limit=limit)

            @post("/users")
            async def create_user(self, user_data: UserCreate) -> User:
                return await self.user_repo.create(user_data)

    The router automatically:
    - Resolves the controller from DI
    - Injects dependencies into the controller
    - Parses query parameters, path parameters, and request body
    - Validates input using Pydantic models
    - Wraps responses in JSONResponse

See Also:
    - :class:`quadkit.web.Controller`: Base controller class.
    - :mod:`quadkit.web.routing.decorators`: HTTP method decorators.
    - :class:`quadkit.web.middleware.Middleware`: Middleware base class.
"""

from collections.abc import Callable
from functools import lru_cache
import inspect
from typing import (
    Any,
    get_origin,
    get_type_hints,
)
import weakref

from starlette.requests import Request

from quadkit.logging import get_logger

logger = get_logger(__name__)


@lru_cache(maxsize=1024)
def _cached_get_type_hints(func: Callable[..., Any]) -> Any:
    """Cached wrapper around typing.get_type_hints(func, globalns=func.__globals__).

    - Caching avoids repeatedly resolving forward refs at request time.
    - Keyed by function object so it's invalidated when the function object is GC'd.
    - Follows __wrapped__ chain to get the original function's __globals__,
      which is necessary when decorators use @functools.wraps and the handler
      has `from __future__ import annotations`.
    """
    target = func
    while hasattr(target, "__wrapped__"):
        target = target.__wrapped__

    globalns = getattr(target, "__globals__", None) or getattr(func, "__globals__", {})
    try:
        return get_type_hints(func, globalns=globalns) or {}
    except (NameError, AttributeError, TypeError):
        try:
            return get_type_hints(target) or {}
        except (NameError, AttributeError, TypeError):
            return {}


from dataclasses import dataclass, field


@dataclass
class Route:
    """Metadata representing a registered route."""

    method: str
    path: str
    handler: Callable
    name: str | None = None
    controller_cls: type | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


from quadkit.web.filters.builtin import (
    DefaultExceptionFilter,
    DependencyResolutionFilter,
    ValidationErrorFilter,
)
from quadkit.web.filters.pipeline import FilterPipeline


class Router:
    """Router with Controller DI Strategy support.

    The Router manages route registration, controller resolution, and
    request handling. It integrates with the DI container to provide
    automatic dependency injection for controllers and their methods.

    Attributes:
        routes: List of registered routes with their handlers.
        _controller_cache: Cache of resolved controller instances.
        _container: DI container for resolving dependencies.
        _signature_cache: Cache of handler signatures for performance.
        _routes_by_name: Dictionary of routes indexed by their unique name.
        exception_filters: Registry for handling controller exceptions.
    """

    def __init__(self, filter_pipeline: FilterPipeline | None = None):
        self.routes: list[Route] = []
        self._routes_by_name: dict[str, Route] = {}
        self._controller_cache: weakref.WeakValueDictionary[type, Any] = (
            weakref.WeakValueDictionary()
        )
        self._container: Any = None
        # Cache for handler signatures (computed once at registration time)
        self._signature_cache: dict[tuple[type, str], dict[str, Any]] = {}
        # Set of (METHOD, path) tuples used to detect duplicate registrations.
        self._route_registry: set[tuple[str, str]] = set()
        self.exception_filters = filter_pipeline or FilterPipeline()
        # Register core filters (last registered runs first, so Default is last fallback)
        self.exception_filters.add_filter(DefaultExceptionFilter())
        self.exception_filters.add_filter(DependencyResolutionFilter())
        self.exception_filters.add_filter(ValidationErrorFilter())

    def get_route_by_name(self, name: str) -> Route | None:
        """Get a route by its unique name in O(1) time.

        Args:
            name: The unique name of the route.

        Returns:
            The Route object if found, otherwise None.
        """
        return self._routes_by_name.get(name)

    def clear_cache(self) -> None:
        """Clear all cached handler signatures and type-hint lookups.

        Call this when modules are hot-reloaded so that stale signatures
        are not used.  The caches will be repopulated lazily on the next
        request that reaches each handler.

        Example::

            hot_reload_manager.on_reload(router.clear_cache)
        """
        self._signature_cache.clear()
        _cached_get_type_hints.cache_clear()

    def _get_handler_signature(
        self,
        controller_cls: type,
        method_name: str,
    ) -> dict[str, Any]:
        """Get cached handler signature or compute and cache it.

        Args:
            controller_cls: The controller class.
            method_name: The method name.

        Returns:
            Dict with 'sig', 'hints', and computed params.
        """
        cache_key = (controller_cls, method_name)
        if cache_key in self._signature_cache:
            return self._signature_cache[cache_key]

        handler = getattr(controller_cls, method_name)
        sig = inspect.signature(handler)

        # Resolve string annotations (cached)
        try:
            hints = _cached_get_type_hints(handler)
        except (NameError, AttributeError, TypeError) as e:
            hints = {}
            logger.debug(
                "Failed to resolve type hints for %s.%s: %s",
                controller_cls.__name__,
                method_name,
                e,
            )

        # Compute DI params info at registration time
        di_params = {}
        body_param = None

        for param_name, param in sig.parameters.items():
            if param_name in ("self", "cls"):
                continue
            if param.annotation is inspect.Parameter.empty:
                continue

            # Determine if this is a DI-injectable param
            origin = get_origin(param.annotation)
            if origin is not None:
                di_params[param_name] = param.annotation

        result = {
            "sig": sig,
            "hints": hints,
            "di_params": di_params,
            "body_param": body_param,
        }

        self._signature_cache[cache_key] = result
        return result

    def _set_container(self, container: Any) -> None:
        """Set the DI container and preload singleton controllers."""
        self._container = container
        if container is None or not hasattr(container, "resolve"):
            return

        # Pre-resolve and cache singleton controllers
        for route in self.routes:
            controller_cls = route.controller_cls
            if controller_cls is not None:
                self._preload_controller(controller_cls)

    def _preload_controller(self, controller_cls: type) -> None:
        """Preload a singleton controller if not already cached."""
        if controller_cls in self._controller_cache:
            return

        if self._container is None or not hasattr(self._container, "resolve"):
            return

        try:
            # Check if controller is a singleton in the container
            if hasattr(
                self._container,
                "is_singleton",
            ) and self._container.is_singleton(controller_cls):
                import asyncio

                # Use sync resolution for singletons if available
                if hasattr(self._container, "resolve"):
                    try:
                        self._controller_cache[controller_cls] = (
                            self._container.resolve(controller_cls)
                        )
                        return
                    except (LookupError, RuntimeError, AttributeError) as exc:
                        logger.debug("controller_sync_resolve_failed", error=str(exc))
                # Fall back to async
                try:
                    try:
                        loop = asyncio.get_running_loop()
                        # Can't synchronously resolve in running loop, skip caching
                        return
                    except RuntimeError:
                        # No running loop, use get_event_loop() for sync operations
                        loop = asyncio.new_event_loop()
                        self._controller_cache[controller_cls] = (
                            loop.run_until_complete(
                                self._container.resolve(controller_cls),
                            )
                        )
                        loop.close()
                except RuntimeError:
                    # No event loop available, skip caching
                    pass
        except (LookupError, RuntimeError, AttributeError) as exc:
            logger.debug(
                "controller_cache_failed", error=str(exc)
            )  # Skip caching if it fails

    def _create_endpoint(
        self,
        controller_cls: type,
        method_name: str,
        container: Any,
    ) -> Callable:
        """
        Creates a wrapper function that:
        1. Resolves the Controller from DI (or uses cached singleton)
        2. Parses request body for Pydantic models
        3. Calls the specific method with proper parameters
        4. Wraps the result in a JSONResponse if not already a Response
        """

        # OPT-WEB-2: Pre-resolve singleton controllers once at route registration time
        cached_controller_instance = None
        # Skip pre-resolving controllers at startup - they may have async dependencies
        # Controllers will be resolved per-request instead
        if container is not None:
            try:
                hasattr(
                    container,
                    "is_singleton",
                ) and container.is_singleton(controller_cls)
                # Don't try to sync resolve controllers - they may have async dependencies
                # Fall through to per-request resolution
            except (LookupError, RuntimeError, AttributeError) as exc:
                logger.debug(
                    "singleton_check_failed", error=str(exc)
                )  # Fall back to per-request resolution

        async def endpoint(request: Request) -> Any:
            try:
                # 1. Resolve scoped container (from DIScopeMiddleware) or use root
                scoped_container = getattr(request.state, "container", None)
                effective_container = scoped_container or container

                # 2. Resolve controller instance
                try:
                    controller_instance = await effective_container.resolve(
                        controller_cls
                    )
                except Exception as _resolve_err:  # noqa: BLE001 — controller resolution may raise any DI error; log before re-raising
                    logger.exception("Failed to resolve controller %s", controller_cls)
                    raise

                # 3. Get handler and pre-computed metadata
                handler = getattr(controller_instance, method_name)
                sig_info = self._get_handler_signature(controller_cls, method_name)
                route = self._get_route_for_handler(handler, method_name)

                # 4. Collect Guards, Interceptors, and Filters
                # Attached via decorators like @use_guards, @intercept, @use_pipes, @use_filters
                guards = getattr(handler, "__guards__", [])
                interceptors = getattr(handler, "__interceptors__", [])
                filters = getattr(handler, "__filters__", [])

                # 5. Build Execution Context
                from quadkit.web.routing.execution_context import WebExecutionContext

                context = WebExecutionContext(
                    request=request,
                    handler=handler,
                    controller_class=controller_cls,
                    method_name=method_name,
                    route_metadata={
                        "sig_info": sig_info,
                        "route": route,
                        **(route.metadata if route else {}),
                    },
                    container=effective_container,
                )

                # 6. Execute through Pipeline
                from quadkit.web.routing.pipeline import RequestPipeline
                from quadkit.web.serialization.serializers import ResponseSerializer

                response_serializer = await effective_container.resolve(
                    ResponseSerializer
                )

                pipeline = RequestPipeline(
                    guards=guards,
                    interceptors=interceptors,
                    filters=filters,
                    fallback_pipeline=self.exception_filters,
                    response_serializer=response_serializer,
                )
                return await pipeline.execute(context)
            except Exception as e:  # noqa: BLE001 — safety net; pipeline setup failures are routed to global exception filters
                # This catch is now a safety net, as the pipeline should handle most things.
                # But if resolution or pipeline setup fails, we still try global filters.
                return await self.exception_filters.handle(e, request)

        return endpoint

    def _create_websocket_endpoint(
        self,
        controller_cls: type,
        method_name: str,
        container: Any,
    ) -> Callable:
        """Creates a WebSocket-compatible endpoint for a controller method.

        Controller ``@websocket`` methods are mounted as Starlette
        ``WebSocketRoute``\\s, which invoke the endpoint with a Starlette
        ``WebSocket`` — not an HTTP ``Request``.  The HTTP endpoint factory
        (:meth:`_create_endpoint`) cannot serve them: its ``Request`` pipeline
        returns before the handshake completes, which surfaces as a 500
        (``ASGI callable returned without completing handshake``).

        This wrapper mirrors :func:`_wrap_websocket_handler` for controller
        methods: it resolves the controller from DI, wraps the Starlette
        socket in the Quadkit :class:`WebSocket` transport, and delegates
        the full connection lifecycle to the decorated method (which
        typically calls ``AbstractWebSocketHandler.handle``).
        """

        async def endpoint(starlette_ws: Any) -> None:
            from quadkit.web.transport.websockets import WebSocket

            # Prefer the container published on the app state (set at boot);
            # fall back to the registration-time container.
            app_state = getattr(getattr(starlette_ws, "app", None), "state", None)
            effective_container = getattr(app_state, "container", None) or container
            if effective_container is None:
                msg = f"No DI container available to resolve {controller_cls!r}"
                raise RuntimeError(msg)

            controller_instance = await effective_container.resolve(controller_cls)
            handler = getattr(controller_instance, method_name)

            await handler(WebSocket(starlette_ws))

        return endpoint

    def _get_route_for_handler(
        self,
        handler: Callable,
        method_name: str,
    ) -> Route | None:
        """Find the Route object for a given handler and method name."""
        return next(
            (
                r
                for r in self.routes
                if r.handler == handler
                or getattr(r.handler, "__name__", None) == method_name
            ),
            None,
        )

    def add_route(
        self,
        method: str,
        path: str,
        handler: Callable,
        name: str | None = None,
        controller_cls: type | None = None,
        **kwargs: Any,
    ) -> None:
        """Add a route (used internally)"""
        route_key = (method.upper(), path)
        if route_key in self._route_registry:
            logger.warning(
                "router.duplicate_route",
                method=method.upper(),
                path=path,
                message="A handler for this method+path is already registered; the earlier registration will be shadowed.",
            )
        self._route_registry.add(route_key)
        route_obj = Route(
            method=method.upper(),
            path=path,
            handler=handler,
            name=name,
            controller_cls=controller_cls,
            metadata=kwargs,
        )
        self.routes.append(route_obj)
        if name:
            self._routes_by_name[name] = route_obj
