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
from dataclasses import dataclass, field
from typing import Any
import weakref

from quadkit.logging import get_logger
from quadkit.web.filters.builtin import (
    DefaultExceptionFilter,
    DependencyResolutionFilter,
    ValidationErrorFilter,
)
from quadkit.web.filters.pipeline import FilterPipeline
from quadkit.web.routing.router_endpoints import RouterEndpointMixin
from quadkit.web.routing.router_signature import (
    RouterSignatureMixin,
    _cached_get_type_hints,
)

logger = get_logger(__name__)


@dataclass
class Route:
    """Metadata representing a registered route."""

    method: str
    path: str
    handler: Callable
    name: str | None = None
    controller_cls: type | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class Router(RouterEndpointMixin, RouterSignatureMixin):
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

    def __init__(
        self,
        filter_pipeline: FilterPipeline | None = None,
        global_pipeline: FilterPipeline | None = None,
    ):
        """Initialize the router.

        Args:
            filter_pipeline: Pipeline holding this router's own filters.
            global_pipeline: Application-wide pipeline owned by the DI
                container; passed down to each request pipeline as the last
                filter consulted before an exception is re-raised.
        """
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
        self.global_pipeline = global_pipeline
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
