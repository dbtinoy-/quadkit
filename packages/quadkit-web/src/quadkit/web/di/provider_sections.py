"""Registration-group sections for :class:`~quadkit.web.di.provider.WebProvider`.

Each function registers one cohesive group of services into the DI
container. They are invoked by ``WebProvider.register()`` at fixed,
ordered positions so the effective registration sequence is identical to
the pre-extraction monolithic implementation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from quadkit.contracts.web import WebProviderProtocol
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.contracts.core.di import ContainerRegistrarProtocol
    from quadkit.web.di.provider import WebProvider
    from quadkit.web.routing.controllers import Controller

logger = get_logger(__name__)


def register_transport_services(
    provider: WebProvider,
    container: ContainerRegistrarProtocol,
) -> None:
    """Register the web provider instance and transport-level singletons."""
    from quadkit.web.di.provider import WebProvider

    container.singleton(WebProvider, provider)
    container.singleton(WebProviderProtocol, provider)

    from quadkit.contracts.web.sse import ReactiveSseBridgeProtocol
    from quadkit.web.transport.reactive import sse_from_stream

    # The DI resolver calls factories with the resolver as an optional
    # argument. Return the bridge callable itself so resolution does not
    # consume a resolver object as the bridge's stream and cache a response.
    container.singleton(
        ReactiveSseBridgeProtocol,
        factory=lambda: sse_from_stream,
    )

    from quadkit.primitives.context import Context, create_default_context

    container.singleton(Context, create_default_context())


def register_security_services(
    provider: WebProvider,
    container: ContainerRegistrarProtocol,
) -> None:
    """Register security configuration objects and the CORS middleware factory."""
    from quadkit.web.security.config import (
        CORSConfig,
        CrossOriginConfig,
        CSPConfig,
        CSRFConfig,
        HSTSConfig,
        SecurityConfig,
    )
    from quadkit.web.security.cors.middleware import CORSMiddlewareFactory

    container.singleton(SecurityConfig, provider.web_config.security)
    container.singleton(CORSConfig, provider.web_config.cors)
    container.singleton(CSRFConfig, provider.web_config.security.csrf)
    container.singleton(HSTSConfig, provider.web_config.security.hsts)
    container.singleton(CSPConfig, provider.web_config.security.csp)
    container.singleton(CrossOriginConfig, provider.web_config.security.cross_origin)
    container.singleton(
        CORSMiddlewareFactory,
        CORSMiddlewareFactory(config=provider.web_config.cors),
    )


def register_routing_services(
    container: ContainerRegistrarProtocol,
    provider: Any = None,
) -> None:
    """Register routing, filtering, serialization, and background-task services.

    The RouteRegistry/ControllerRegistry singletons are the provider's
    per-application instances (plans/09172026 H-04) when a provider is
    supplied; DI resolution and the admin pages then observe exactly the
    routes mounted on that application. Without a provider the singletons
    are freshly created instances (standalone container use).
    """
    from quadkit.web.routing.controller_registry import ControllerRegistry
    from quadkit.web.routing.registry import RouteRegistry

    # NB: explicit None checks — an empty Registry is falsy (len == 0), so
    # an `or` fallback would silently swap in a fresh instance.
    route_registry = getattr(provider, "route_registry", None)
    if route_registry is None:
        route_registry = RouteRegistry()
    container.singleton(RouteRegistry, route_registry)

    controller_registry = getattr(provider, "controller_registry", None)
    if controller_registry is None:
        controller_registry = ControllerRegistry()
    container.singleton(ControllerRegistry, controller_registry)

    # The application-wide FilterPipeline is a container singleton built from
    # the provider's `filters` list — no module-level instance exists, so two
    # applications in one process cannot share (or mutate) each other's
    # pipeline, and injecting FilterPipeline yields the same object the
    # request path consults.
    from quadkit.logging.debug import is_debug_mode
    from quadkit.web.filters.pipeline import FilterPipeline

    global_pipeline = FilterPipeline(
        debug=is_debug_mode() or provider.web_config.server.debug,
    )
    for filter_instance in getattr(provider, "filters", None) or []:
        global_pipeline.add_filter(filter_instance)
    container.singleton(FilterPipeline, global_pipeline)

    from quadkit.web.interceptors.pipeline import InterceptorPipeline

    container.singleton(InterceptorPipeline, InterceptorPipeline())

    # Register Router for dependency injection (pre-instantiated so the DI
    # framework does not inject the FilterPipeline singleton into it and
    # accidentally pollute the global filter pipeline with Router-local filters).
    from quadkit.web.routing.router import Router

    container.singleton(Router, Router())

    # Register ResponseFactoryProtocol
    from quadkit.contracts.web import ResponseFactoryProtocol
    from quadkit.web.responses import StarletteResponseAdapter

    container.singleton(ResponseFactoryProtocol, StarletteResponseAdapter)

    # Register ResponseSerializer so the router can resolve it per-request
    # without hitting an UnresolvableDependencyError.
    from quadkit.web.serialization.serializers import ResponseSerializer

    container.singleton(ResponseSerializer, ResponseSerializer())

    # Register BackgroundTaskRunnerProtocol — per-resolution (transient) so each
    # caller gets an independent task accumulator bound to its own Starlette context.
    # Background tasks are in-process only. Durable job submission uses explicit
    # the optional provider job APIs, not this web background-runner interface.
    from quadkit.contracts.web.protocols import BackgroundTaskRunnerProtocol
    from quadkit.web.background.tasks import StarletteBackgroundTaskRunner

    container.transient(
        cast("Any", BackgroundTaskRunnerProtocol),
        cast("Any", StarletteBackgroundTaskRunner),
    )


def register_admin_services(
    container: ContainerRegistrarProtocol,
) -> None:
    """Register admin widget handlers and the admin contributor."""
    # Register admin widget handlers (transient for scope safety)
    from quadkit.web.admin.contributor import WebAdminContributor
    from quadkit.web.admin.handlers.active_connections import (
        ActiveConnectionsWidgetHandler,
    )
    from quadkit.web.admin.handlers.request_rate import (
        RequestRateWidgetHandler,
    )
    from quadkit.web.admin.handlers.server_status import (
        ServerStatusWidgetHandler,
    )

    container.transient(ServerStatusWidgetHandler, ServerStatusWidgetHandler)
    container.transient(
        ActiveConnectionsWidgetHandler,
        ActiveConnectionsWidgetHandler,
    )
    container.transient(RequestRateWidgetHandler, RequestRateWidgetHandler)
    container.singleton(WebAdminContributor, WebAdminContributor)


def merge_contributed_extensions(
    provider: WebProvider,
    container: ContainerRegistrarProtocol,
) -> None:
    """Register the contributor registry singleton and merge entry-point contributors."""
    from quadkit.web.contributors import WebContributorRegistry
    from quadkit.web.contributors import discovery as contributor_discovery

    # Register the web contributor registry as a singleton
    container.singleton(WebContributorRegistry, provider._contributor_registry)

    # Discover and merge web contributors from entry-points, skipping
    # contributor IDs the host excluded via WebConfig (no registry entry,
    # no contributed controllers/middleware, no mounted routes).
    excluded = set(getattr(provider.web_config, "excluded_contributors", None) or [])
    for contributor in contributor_discovery.load_web_contributors():
        if contributor.contributor_id in excluded:
            logger.debug(
                "web.contributor_excluded",
                contributor_id=contributor.contributor_id,
            )
            continue
        provider._contributor_registry.register(contributor)

        # Merge contributed middleware (avoid duplicates)
        for middleware_cls in contributor.get_middleware():
            if middleware_cls not in provider.middleware:
                provider.middleware.append(middleware_cls)

        # Merge contributed controllers (avoid duplicates and
        # subclass-takes-precedence — if a subclass of the contributed
        # controller is already registered, skip the contributed one).
        for controller_cls in contributor.get_controllers():
            if controller_cls not in provider.controllers:
                # Skip if a registered controller is a subclass — the
                # user-supplied override should take precedence over the
                # framework's own controller.
                if isinstance(controller_cls, type) and any(
                    isinstance(ec, type)
                    and ec is not controller_cls
                    and issubclass(ec, controller_cls)
                    for ec in provider.controllers
                ):
                    continue
                provider.controllers.append(controller_cls)


def register_controller_singletons(
    container: ContainerRegistrarProtocol,
    controllers: list[type[Controller]],
) -> None:
    """Register controller classes as container singletons.

    A controller that a feature provider already registered — typically
    with a richer factory that closes over provider state (e.g. the
    GraphQLProvider binding ``GraphQLController`` to itself) — keeps its
    existing registration.  Overwriting it here would replace the bound
    instance with an unbound one and break request-time resolution.
    """
    # Register controllers as singletons if they are classes and unregistered
    for controller_cls in controllers:
        if isinstance(controller_cls, type) and not container.has(controller_cls):
            container.singleton(controller_cls, controller_cls)


def register_middleware_registries(
    provider: WebProvider,
    container: ContainerRegistrarProtocol,
) -> None:
    """Expose the active middleware pipeline via registry singletons."""
    # Expose the active middleware pipeline to admin pages and tooling.
    # The registry mirrors exactly what the app runs: the always-present
    # DIScopeMiddleware plus contributed and user-supplied middleware.
    from quadkit.web.middleware.base import MiddlewareRegistry
    from quadkit.web.middleware.di_scope import DIScopeMiddleware
    from quadkit.web.middleware.registry import (
        MiddlewareAdapterRegistry,
    )

    middleware_registry = MiddlewareRegistry()
    middleware_registry.register_middleware(DIScopeMiddleware)
    for middleware_cls in provider.middleware:
        cls = (
            middleware_cls if isinstance(middleware_cls, type) else type(middleware_cls)
        )
        middleware_registry.register_middleware(cls)
    container.singleton(MiddlewareRegistry, middleware_registry)
    container.singleton(
        MiddlewareAdapterRegistry,
        MiddlewareAdapterRegistry.with_defaults(),
    )


def register_injectable_services(
    provider: WebProvider,
    container: ContainerRegistrarProtocol,
) -> None:
    """Register services explicitly provided via ``_extra_injectable_services``.

    This replaces the former sys.modules scanning with explicit service lists,
    making DI registration deterministic and order-independent. Services must be
    explicitly provided to the provider at construction time.
    """
    from quadkit.contracts.core.scopes import ServiceScope

    def _register_one(cls: type, scope: Any) -> None:
        if container.has(cls):
            return
        if scope == ServiceScope.SINGLETON:
            container.singleton(cls, cls)
        elif scope == ServiceScope.SCOPED:
            container.scoped(cls, cls)
        else:
            container.transient(cls, cls)
        logger.debug("auto_registered_injectable", cls=cls.__name__, scope=scope)

    # Register only explicitly provided services
    for cls, scope in provider._extra_injectable_services:
        _register_one(cls, scope)
