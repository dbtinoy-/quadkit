"""Parameter binder for web handlers.

Resolves handler arguments from HTTP requests, supporting multiple sources
(Path, Query, Body, Header, Cookie), DI, and special types.
"""

from __future__ import annotations

import inspect
from typing import Any, cast

from quadkit.logging import get_logger
from quadkit.web.exceptions import DependencyResolutionError
from quadkit.web.protocols import ExecutionContextProtocol
from quadkit.web.routing.execution_context import WebExecutionContext

logger = get_logger(__name__)


class ParameterBinder:
    """Binds request data to handler parameters."""

    def __init__(self, sig: inspect.Signature, hints: dict[str, Any]):
        """Initialize the binder.

        Args:
            sig: The handler signature.
            hints: Resolved type hints for the handler.
        """
        self.sig = sig
        self.hints = hints

    async def bind(self, context: WebExecutionContext) -> dict[str, Any]:
        """Bind request data to parameters for the current context.

        Args:
            context: The execution context containing the request and container.

        Returns:
            Dictionary of keyword arguments for the handler call.
        """
        from quadkit.web.routing.validation import validate_and_merge_request

        request = context.request
        handler = context.handler
        container = context.container

        kwargs = {}
        path_params = getattr(request, "path_params", {}) or {}

        # 1. Pydantic Validation & Merging (Unified Sources)
        # This handles Body DTOs, Query params, and Path params that are part of a model.
        parsed_all = None
        try:
            parsed_all = await validate_and_merge_request(
                request,
                handler,
                path_params,
            )
        except (ValueError, TypeError):
            # Re-raise for exception filters
            raise

        # 2. Map parameters to handler signature
        for param_name, param in self.sig.parameters.items():
            if param_name == "self":
                continue

            annotation = self.hints.get(param_name, param.annotation)
            value = None

            # Resolve ForwardRef strings if needed
            if isinstance(annotation, str):
                resolved = handler.__globals__.get(annotation)
                if resolved is not None:
                    annotation = resolved

            # A. Check parsed validation result (Path/Query/Body DTOs)
            if parsed_all and hasattr(parsed_all, param_name):
                value = getattr(parsed_all, param_name)

            # B. Special Type: Request or ExecutionContextProtocol
            elif self._is_request_type(annotation, param_name):
                value = request

            elif annotation in (WebExecutionContext, ExecutionContextProtocol):
                value = context

            # C. Dependency Injection
            elif (
                container
                and hasattr(container, "resolve")
                and annotation is not inspect.Parameter.empty
            ):
                # Only resolve if NOT already found in path/query (to allow overrides)
                if (
                    param_name not in path_params
                    and param_name not in request.query_params
                ):
                    try:
                        value = await container.resolve(annotation)
                    except Exception as e:  # noqa: BLE001 — container.resolve may raise any DI error; wrap into typed DependencyResolutionError
                        if param.default is inspect.Parameter.empty:
                            raise DependencyResolutionError(
                                param=param_name,
                                service_type=annotation,
                                cause=e,
                            ) from e

            # D. Manual Fallbacks (Direct extraction)
            if value is None:
                if param_name in path_params:
                    value = path_params[param_name]
                elif param_name in request.query_params:
                    value = request.query_params[param_name]
                elif param.default is not inspect.Parameter.empty:
                    # If it's a decorator, get its default
                    if hasattr(param.default, "_quadkit_param_info"):
                        value = param.default._quadkit_param_info.get("default")
                    else:
                        value = param.default

                if value is ...:
                    value = None

            # 3. Execute Pipes
            value = await self._run_pipes(param_name, value, param, annotation, context)
            kwargs[param_name] = value

        return kwargs

    async def _run_pipes(
        self,
        name: str,
        value: Any,
        param: inspect.Parameter,
        annotation: Any,
        context: WebExecutionContext,
    ) -> Any:
        """Execute pipes for a single parameter."""
        from quadkit.web.protocols import ParamMetadata

        # Collect pipes
        pipes = []

        # 1. Parameter-level pipes
        info = getattr(param.default, "_quadkit_param_info", {})
        if info and "pipes" in info and info["pipes"]:
            pipes.extend(info["pipes"])

        # 2. Handler-level pipes (@use_pipes)
        handler_pipes = getattr(context.handler, "_quadkit_pipes", [])
        pipes.extend(handler_pipes)

        if not pipes:
            return value

        # Create metadata for pipes
        metadata = ParamMetadata(
            name=name,
            param_type=info.get("type", "unknown"),
            expected_type=annotation
            if annotation is not inspect.Parameter.empty
            else None,
            default=info.get("default") if info.get("default") is not ... else None,
            alias=info.get("alias"),
        )

        result = value
        for pipe in pipes:
            # If pipe is a class, instantiate it (simple DI could be added here later)
            pipe_instance = cast("Any", pipe()) if inspect.isclass(pipe) else pipe
            result = await pipe_instance.transform(result, metadata)

        return result

    def _is_request_type(self, annotation: Any, name: str) -> bool:
        """Helper to determine if a parameter represents the Request object."""
        try:
            annotation_name = getattr(annotation, "__name__", None)
        except AttributeError:
            annotation_name = None

        from starlette.requests import Request as StarletteRequest

        return (
            annotation is StarletteRequest
            or annotation_name == "Request"
            or str(annotation).startswith("Request")
            or name == "request"
        )


__all__ = ["ParameterBinder"]
