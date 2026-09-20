"""Endpoint factories for the router.

Every controller method is served by a closure created at registration time:
resolve the controller through DI, assemble the guard/interceptor/filter
pipeline for the route, and hand the request to the request pipeline.
WebSocket methods get their own factory — their transport is a Starlette
``WebSocket``, not an HTTP ``Request``, and the request pipeline returns before
the handshake completes.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from starlette.requests import Request

from quadkit.logging import get_logger
from quadkit.web.filters.pipeline import FilterPipeline
from quadkit.web.routing.router_signature import RouterSignatureMixin

if TYPE_CHECKING:
    import weakref

    from quadkit.web.routing.router import Route

logger = get_logger(__name__)


class RouterEndpointMixin(RouterSignatureMixin):
    """Endpoint factories that wrap controller methods for the app."""

    if TYPE_CHECKING:
        # Collaborators provided by Router on composition.
        _container: Any
        _controller_cache: weakref.WeakValueDictionary[type, Any]
        routes: list[Route]
        exception_filters: FilterPipeline
        global_pipeline: FilterPipeline | None

        def _get_route_for_handler(
            self,
            handler: Callable,
            method_name: str,
        ) -> Route | None: ...

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
        # plans/09172026 R-05: compute the zero-binding fast path once at wrap
        # time so request-time parameter binding can be skipped entirely for
        # handlers whose only parameters are request/context injections.
        simple_binding = self._compute_simple_binding(controller_cls, method_name)
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
                # Attached via decorators like @use_guards, @use_interceptors, @use_filters
                guards = getattr(handler, "__guards__", [])
                handler_interceptors = getattr(handler, "__interceptors__", None)
                if handler_interceptors is None:
                    handler_interceptors = getattr(
                        controller_cls, "__interceptors__", []
                    )
                interceptors = list(handler_interceptors)
                # Application-wide interceptors live on the container-registered
                # InterceptorPipeline singleton and run before route-level ones.
                try:
                    from quadkit.web.interceptors.pipeline import InterceptorPipeline

                    global_pipeline = await effective_container.resolve(
                        InterceptorPipeline
                    )
                except (LookupError, RuntimeError):
                    global_pipeline = None
                if global_pipeline is not None:
                    interceptors = list(global_pipeline.interceptors) + interceptors
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
                        "simple_binding": simple_binding,
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
                    global_pipeline=self.global_pipeline,
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
