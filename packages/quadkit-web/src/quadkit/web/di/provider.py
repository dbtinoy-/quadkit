"""WebProvider - Main web provider with pass-through architecture"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from starlette.applications import Starlette
from starlette.responses import JSONResponse

from quadkit.contracts.core import (
    HealthCheckResult,
    HealthStatus,
    HookRegistryProtocol,
    ProviderPriority,
)
from quadkit.contracts.core.di import (
    ContainerRegistrarProtocol,
    ContainerResolverProtocol,
)
from quadkit.contracts.exceptions.config import ConfigurationError
from quadkit.di.provider import Provider
from quadkit.logging import get_logger
from quadkit.web.config import WebConfig, WebProviderConfig
from quadkit.web.di import provider_sections
from quadkit.web.di.middleware_setup import MiddlewareSetup
from quadkit.web.di.route_setup import RouteSetup
from quadkit.web.docs.generator import OpenAPIGenerator
from quadkit.web.integrations.auth import AuthIntegration
from quadkit.web.integrations.cache import CacheIntegration
from quadkit.web.integrations.graphql import GraphQLIntegration
from quadkit.web.integrations.rate_limit import RateLimitIntegration
from quadkit.web.integrations.setup import lifespan
from quadkit.web.integrations.sql import SQLIntegration
from quadkit.web.middleware.manager import WebMiddlewareManager
from quadkit.web.routing.controllers import Controller
from quadkit.web.routing.manager import WebRouterManager
from quadkit.web.routing.router import Router

# Optional external server - imported lazily to avoid dependency issues
# Only needed when run_server() is called

logger = get_logger(__name__)


class WebProvider(Provider):
    """Web provider with native Starlette integration and pass-through architecture.

    **Recommended usage** — let the orchestrator inject configuration via
    ``application.yaml`` (uses ``config_key = "web"`` and ``config_model = WebConfig``)::

        app.add_provider(WebProvider())

    **Config-first factory** — construct from an explicit ``WebConfig``::

        from quadkit.web import WebProvider, WebConfig

        app.add_provider(WebProvider.from_config(WebConfig(debug=True, ...)))

    **Advanced** — pass individual components explicitly (e.g. for tests)::

        app.add_provider(WebProvider(
            controllers=[UsersController],
            middleware=[AuthMiddleware],
            web_config=WebConfig(debug=True),
        ))

    Note: The multi-parameter constructor is intended for advanced and test
    scenarios.  For typical applications, prefer the no-arg or ``from_config()``
    form so that configuration is driven by ``application.yaml``.
    """

    name = "web"
    priority = ProviderPriority.PRESENTATION

    config_key: str | None = "web"
    config_model: type[Any] | None = WebConfig

    def __init__(
        self,
        middleware: list[Any] | None = None,
        exception_handlers: dict[Any, Any] | None = None,
        controllers: list[type[Controller]] | None = None,
        web_config: WebConfig | None = None,
        provider_config: WebProviderConfig | None = None,
        debug_routes_auth: Callable[..., Any] | None = None,
        websocket_handlers: list[type] | None = None,
    ) -> None:
        super().__init__()
        self.middleware = middleware or []
        self.exception_handlers = exception_handlers or {}
        self.controllers = controllers or []
        self.websocket_handlers = websocket_handlers or []

        self.web_config = web_config or WebConfig()
        self._explicit_web_config = web_config is not None
        self.provider_config = provider_config or WebProviderConfig()

        self.starlette: Starlette | None = None
        self._hook_registry: HookRegistryProtocol | None = None

        # Managers
        self.middleware_manager = WebMiddlewareManager(self)
        self.router_manager: WebRouterManager = WebRouterManager(self)

        # Per-application registries (plans/09172026 H-04): every provider
        # instance owns its own route/controller registry pair so two
        # applications in one process never see each other's routes. These
        # are the instances registered with the DI container and mirrored
        # by the router manager during discovery.
        from quadkit.web.routing.controller_registry import ControllerRegistry
        from quadkit.web.routing.registry import RouteRegistry

        self._route_registry = RouteRegistry()
        self._controller_registry = ControllerRegistry()

        # Internal state for routing
        self.router: Router | None = None  # Lazy loaded if needed
        self.openapi_generator: OpenAPIGenerator | None = None

        # Route conflict behavior (default: do not raise on duplicate routes)
        # Tests expect duplicate registrations to emit warnings unless explicitly configured
        self.fail_on_route_conflict = getattr(
            self.provider_config,
            "fail_on_route_conflict",
            False,
        )

        # Debug routes config
        self.debug_routes_auth: Callable[..., Any] | None = debug_routes_auth
        self._debug_redis_client: Any | None = None

        # Extra services to register in DI (used by quickstart auto-injection)
        self._extra_injectable_services: list[tuple[type, Any]] = []

        # Web contributor registry for entry-point-based controller/middleware discovery
        from quadkit.web.contributors import WebContributorRegistry

        self._contributor_registry: WebContributorRegistry = WebContributorRegistry()

    @property
    def contributor_registry(self) -> Any:
        """Expose contributor registry for route setup access."""
        return self._contributor_registry

    @property
    def route_registry(self) -> Any:
        """This application's route registry (per-instance, plans/09172026 H-04)."""
        return self._route_registry

    @property
    def controller_registry(self) -> Any:
        """This application's controller registry (per-instance, H-04)."""
        return self._controller_registry

    @classmethod
    def from_config(cls, config: WebConfig, **context: Any) -> WebProvider:
        """Create a WebProvider from config.

        Context kwargs may include middleware, controllers, exception_handlers.
        """
        return cls(
            web_config=config,
            middleware=context.get("middleware"),
            controllers=context.get("controllers"),
            websocket_handlers=context.get("websocket_handlers"),
            exception_handlers=context.get("exception_handlers"),
        )

    @classmethod
    def auto_discover(
        cls,
        *packages: str,
        web_config: WebConfig | None = None,
        **kwargs: Any,
    ) -> WebProvider:
        """Create a WebProvider with routes auto-discovered from packages.

        Scans each package recursively for
        :class:`~quadkit.web.routing.controllers.Controller` subclasses and
        ``@websocket_handler`` classes, registering both automatically.

        Args:
            *packages: Dotted Python package paths to scan for controllers and
                WebSocket handlers, e.g. ``"my_app.api"``.
            web_config: Optional web configuration. Falls back to defaults.
            **kwargs: Extra kwargs forwarded to :class:`WebProvider.__init__`.

        Returns:
            A configured :class:`WebProvider` instance.

        Example::

            app.add_provider(WebProvider.auto_discover("my_app.api.controllers"))
        """
        from quadkit.web.routing.discovery import (
            discover_controllers,
            discover_websocket_handlers,
        )

        controllers = discover_controllers(list(packages))
        websocket_handlers = discover_websocket_handlers(list(packages))
        return cls(
            controllers=controllers,
            websocket_handlers=websocket_handlers,
            web_config=web_config,
            **kwargs,
        )

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        """Register web services in DI container.

        Delegates each cohesive registration group to
        :mod:`quadkit.web.di.provider_sections`, invoked at the same ordered
        positions as the pre-extraction implementation.
        """

        # Reconcile the orchestrator-injected yaml section with the
        # constructor fallback: when no explicit web_config was passed to
        # configure(), self.web_config still holds WebConfig() defaults while
        # self.config now carries the real [web] section. Prefer the injected
        # truth so middleware/rate-limit setup sees yaml values.
        if self.config is not None and not self._explicit_web_config:
            self.web_config = self.config

        # GuardProtocol: debug routes with no protection would expose the entire DI graph.
        # Require at least one protection mechanism: a token or an auth callback.
        if (
            self.web_config.debug_routes
            and not self.web_config.debug_routes_token
            and self.debug_routes_auth is None
        ):
            raise ConfigurationError(
                "debug_routes=True requires either debug_routes_token (in WebConfig) "
                "or a debug_routes_auth callback (in WebProvider). "
                "Set one to protect the debug endpoint."
            )

        provider_sections.register_transport_services(self, container)

        provider_sections.register_security_services(self, container)

        provider_sections.register_routing_services(container, self)

        provider_sections.register_admin_services(container)

        provider_sections.merge_contributed_extensions(self, container)

        provider_sections.register_controller_singletons(container, self.controllers)

        provider_sections.register_middleware_registries(self, container)

        # Auto-register user classes decorated with @singleton / @injectable.
        # Scan loaded non-framework modules so script-mode apps work without
        # manually calling container.singleton() for each service.
        provider_sections.register_injectable_services(self, container)

    async def boot(self, container: ContainerResolverProtocol) -> None:
        """Initialize the web layer in five ordered phases.

        Phase 1 — OpenAPI generator
            Instantiates :class:`~quadkit.web.routing.OpenAPIGenerator` with
            title and version from :attr:`web_config`.

        Phase 2 — Starlette application
            Builds the native ASGI ``Starlette`` instance.  The middleware stack
            is composed **once** here; it is never rebuilt at request time.
            Container and config are attached to ``app.state``.

        Phase 3 — Middleware pipeline
            Iterates registered :class:`~quadkit.web.middleware.AbstractMiddleware`
            subclasses and wraps the Starlette app.  Order follows the provider
            registration order (outermost-first).

        Phase 4 — Integration setup
            Wires optional first-class integrations: authentication, rate
            limiting, GraphQL gateway.  Each integration is only activated when
            its config key is present in the resolved container.

        Phase 5 — Route registration
            Discovers annotated controller methods and mounts them on the
            Starlette router.  Route-level dependencies (guards, interceptors,
            serializers) are resolved here.
        """
        logger.info("Booting WebProvider")

        # Create FilterPipeline with debug mode based on environment
        from quadkit.logging.debug import is_debug_mode
        from quadkit.web.filters.pipeline import FilterPipeline

        _debug_mode = is_debug_mode() or self.web_config.server.debug
        self.router = Router(filter_pipeline=FilterPipeline(debug=_debug_mode))
        # Application-level exception handler mappings dispatch through the
        # router filter pipeline: the route-level safety net resolves every
        # route-raised error there, before built-in global filters run.
        if self.exception_handlers:
            from quadkit.web.filters.adapters import CallbackExceptionFilter

            for exc_type, handler in self.exception_handlers.items():
                self.router.exception_filters.add_filter(
                    CallbackExceptionFilter(exc_type, handler)
                )
        self._hook_registry = await container.resolve_optional(HookRegistryProtocol)

        # 1. Initialize OpenAPI generator
        self.openapi_generator = OpenAPIGenerator(
            title=str(getattr(self.web_config, "openapi_title", "Quadkit API")),
            version=str(getattr(self.web_config, "openapi_version", "0.1.0")),
        )

        # 2. Initialize native Starlette app
        self.starlette = self._init_starlette(container)
        self.starlette.state.hook_registry = self._hook_registry

        # 3. Setup Middlewares
        await self._setup_middleware(self.starlette, container)

        # 4. Setup Integrations (Auth, Rate Limit, GraphQL)
        await self._setup_integrations(self.starlette, container)

        # 5. Register Routes
        await self._setup_routes(self.starlette, container)

        # 6. Boot admin contributor
        from quadkit.web.admin.contributor import WebAdminContributor

        contributor = await container.resolve_optional(WebAdminContributor)
        if contributor is not None:
            await contributor.on_admin_boot(container)

        logger.info("Web application startup complete")

    def _init_starlette(self, container: ContainerResolverProtocol) -> Starlette:
        """Initialize the Starlette application instance."""
        from quadkit.web.integrations.starlette import build_starlette_app

        # Build initial middleware stack
        native_middleware = self.middleware_manager.build_native_stack(container)

        return build_starlette_app(
            middleware=native_middleware,
            exception_handlers=self.exception_handlers,
            lifespan=lifespan,
            container=container,
        )

    async def _setup_middleware(
        self, app: Starlette, container: ContainerResolverProtocol
    ) -> None:
        """Configure application-level middlewares via :class:`MiddlewareSetup`."""
        setup = MiddlewareSetup(self.web_config, hooks=self._hook_registry)
        await setup.configure(app, container)

        # Single-source-of-truth invariant: log the final ordered stack
        # (outermost first) exactly once. The DI-scope layer comes from the
        # native stack built at Starlette construction — configure() never
        # re-adds it, so it must appear here exactly once.
        logger.info(
            "middleware_stack_configured",
            middleware=[mw.cls.__name__ for mw in app.user_middleware],
        )

    async def _setup_integrations(
        self, app: Starlette, container: ContainerResolverProtocol
    ) -> None:
        """Configure external integrations and complex subsystems."""
        # 1. Rate Limiting
        await RateLimitIntegration.configure(
            app, cast("Any", container), self.web_config
        )

        # 2. Authentication
        if self.web_config.enable_auth:
            await AuthIntegration.configure(
                app, cast("Any", container), self.web_config
            )

        # 3. GraphQL - WebSocket routes (HTTP handled by web contributor)
        await GraphQLIntegration.configure(app, container)

        # 4. SQL Integration - attach db_pool to app.state for lifespan cleanup
        await SQLIntegration.configure(app, container)

        # 5. Cache Integration - attach redis_client to app.state for lifespan cleanup
        await CacheIntegration.configure(app, container)

        # 6. Default exception filter (handles DomainError, HTTPError, etc.)
        from quadkit.logging.debug import is_debug_mode
        from quadkit.web.filters import DefaultExceptionFilter

        _debug_on = is_debug_mode() or self.web_config.server.debug
        default_filter = DefaultExceptionFilter(debug=_debug_on)
        if not hasattr(app.state, "exception_filters"):
            app.state.exception_filters = []
        app.state.exception_filters.append(default_filter)

        # 5. Global Exception Handlers
        from quadkit.web.exceptions import DependencyResolutionError

        app.add_exception_handler(
            DependencyResolutionError,
            self._dependency_resolution_handler,
        )

    async def _setup_routes(
        self, app: Starlette, container: ContainerResolverProtocol
    ) -> None:
        """Register application routes and mounts via :class:`RouteSetup`."""
        setup = RouteSetup(self.web_config, self.provider_config, self.router_manager)
        await setup.configure(app, container, provider_context=self)

    # -- Handlers ----------------------------------------------------------

    def _dependency_resolution_handler(
        self, request: Any, exc: Exception
    ) -> JSONResponse:
        return JSONResponse(
            {
                "error": "dependency_resolution_error",
                "message": str(exc),
                "details": getattr(exc, "details", {}),
            },
            status_code=500,
        )

    async def shutdown(self) -> None:
        """Cleanup resources created by this provider."""
        logger.info("Shutting down WebProvider...")
        self._debug_redis_client = None
        self._hook_registry = None
        self.starlette = None
        logger.info("WebProvider shutdown complete")

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Check web provider health."""
        return HealthCheckResult(
            component="web",
            status=HealthStatus.HEALTHY
            if self.starlette is not None
            else HealthStatus.UNHEALTHY,
            details={
                "starlette_initialized": self.starlette is not None,
            },
        )

    def run_server(
        self,
        host: str = "127.0.0.1",
        port: int = 8000,
        **kwargs: Any,
    ) -> None:
        """Run the web application synchronously (blocking).

        Delegates to :func:`quadkit.web.server.runner.run_server`, which
        is sync-only; call :func:`quadkit.web.server.runner.run_server_async`
        from async code instead.
        """
        from quadkit.web.server.runner import run_server as _run_server

        if self.starlette is None:
            raise RuntimeError(
                "Starlette app not initialized. Call boot() on the provider first."
            )

        _run_server(self.starlette, host=host, port=port, **kwargs)


__all__ = ["WebProvider"]
