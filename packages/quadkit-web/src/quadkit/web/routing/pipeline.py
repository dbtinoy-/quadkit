"""Web request execution pipeline.

Orchestrates the execution of guards, interceptors, and handlers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.web.interceptors.pipeline import InterceptorChain

if TYPE_CHECKING:
    from quadkit.contracts.web.guard import GuardProtocol
    from quadkit.contracts.web.protocols import ExceptionFilterProtocol
    from quadkit.web.filters.pipeline import FilterPipeline
    from quadkit.web.protocols import WebInterceptorProtocol
    from quadkit.web.routing.execution_context import WebExecutionContext
    from quadkit.web.serialization.serializers import ResponseSerializer


class RequestPipeline:
    """Orchestrates the request execution lifecycle."""

    def __init__(
        self,
        guards: list[GuardProtocol] | None = None,
        interceptors: list[WebInterceptorProtocol] | None = None,
        filters: list[ExceptionFilterProtocol] | None = None,
        fallback_pipeline: FilterPipeline | None = None,
        response_serializer: ResponseSerializer | None = None,
    ):
        """Initialize the pipeline.

        Args:
            guards: List of guards to execute.
            interceptors: List of interceptors to execute.
            filters: List of exception filters to execute.
            fallback_pipeline: Optional fallback pipeline (e.g. from the Router).
            response_serializer: Optional pre-wired ResponseSerializer instance.
        """
        self.guards = guards or []
        self.interceptors = interceptors or []
        self.filters = filters or []
        self.fallback_pipeline = fallback_pipeline
        self.response_serializer = response_serializer

    async def execute(self, context: WebExecutionContext) -> Any:
        """Execute the pipeline for the given context.

        Args:
            context: The execution context.

        Returns:
            The result of the handler (possibly transformed).
        """
        try:
            # 1. Execute Guards
            for guard in self.guards:
                if not await guard.can_activate(context):
                    from quadkit.web.exceptions import ForbiddenError

                    raise ForbiddenError("Access denied by guard")

            # 2. Execute Interceptors & Handler
            # We wrap the final handler call in a CallHandlerProtocol to be used by interceptors
            async def final_handler() -> Any:
                # plans/09172026 R-05 fast path: when every handler parameter
                # is a request or execution-context injection (precomputed at
                # route-wrap time), parameter binding and request validation
                # are no-ops — call the handler directly without constructing
                # a ParameterBinder or running validate_and_merge_request.
                simple_binding = context.route_metadata.get("simple_binding")
                if simple_binding is not None:
                    kwargs = {
                        name: (context.request if source == "request" else context)
                        for name, source in simple_binding.items()
                    }
                    return await context.handler(**kwargs)

                from quadkit.web.routing.parameter_binder import ParameterBinder

                # Resolve parameters using binder
                sig_info = context.route_metadata.get("sig_info")
                if not sig_info:
                    # Fallback to computing on the fly (less efficient)
                    import inspect

                    from quadkit.web.routing.validation import (
                        _cached_get_type_hints_for_handler,
                    )

                    sig = inspect.signature(context.handler)
                    hints = _cached_get_type_hints_for_handler(context.handler)
                    sig_info = {"sig": sig, "hints": hints}

                binder = ParameterBinder(sig_info["sig"], sig_info["hints"])
                kwargs = await binder.bind(context)

                return await context.handler(**kwargs)

            # Build interceptor chain
            chain = InterceptorChain(self.interceptors, 0, final_handler, context)
            result = await chain.handle()

            # 3. Post-execution: Serialize result to Response if needed
            from starlette.responses import Response as StarletteResponse

            # 3.0 Peel ``(payload, BackgroundTasks)``: queued work attaches to
            # the outgoing response and runs after it is sent.
            from quadkit.web.background.tasks import BackgroundTasks

            background_task: Any = None
            if (
                isinstance(result, tuple)
                and len(result) == 2
                and isinstance(result[1], BackgroundTasks)
            ):
                result, tasks = result
                background_task = tasks._to_starlette_task()  # noqa: SLF001

            if isinstance(result, StarletteResponse):
                if background_task is not None:
                    result.background = background_task
                return result

            from quadkit.web.serialization.serializers import ResponseSerializer

            route = context.route_metadata.get("route")
            serializer = self.response_serializer or ResponseSerializer()

            response = await serializer.serialize(
                result,
                context.request,
                route=route,
            )
            if background_task is not None:
                response.background = background_task
            return response

        except Exception as e:  # noqa: BLE001 — pipeline safety net; dispatches any error to registered exception filters
            # Match and execute appropriate filter
            # Local filters take precedence
            for f in reversed(self.filters):
                if f.can_handle(e):
                    return await f.handle(e, context.request)

            # Check for fallback pipeline (e.g. from the Router)
            if self.fallback_pipeline:
                return await self.fallback_pipeline.handle(e, context.request)

            # Check for truly global filters if no fallback handled it
            from quadkit.web.filters.pipeline import get_filter_pipeline

            global_pipeline = get_filter_pipeline(context.container)
            if global_pipeline and global_pipeline is not self.fallback_pipeline:
                return await global_pipeline.handle(e, context.request)

            # Re-raise if no filter found
            raise


__all__ = ["RequestPipeline"]
