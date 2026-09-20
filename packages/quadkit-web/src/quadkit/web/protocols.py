"""Web-layer protocols for pipes and interceptors.

Defines the interfaces used exclusively within quadkit-web:

- Pipe layer: ``PipeProtocol``, ``ParamMetadata``, ``body`` helper.
- Interceptor layer: ``ExecutionContextProtocol`` (sourced from contracts so
  that ``GuardProtocol`` in contracts can also reference it without a
  dependency inversion), ``CallHandlerProtocol``, ``WebInterceptorProtocol``,
  ``WebInterceptorBase``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from quadkit.contracts.web.execution_context import ExecutionContextProtocol

# =============================================================================
# Pipe Protocols
# =============================================================================


@dataclass
class ParamMetadata:
    """Metadata about a parameter being piped.

    Attributes:
        name: The parameter name.
        param_type: The type of parameter (path, query, body, header, cookie, file).
        expected_type: The expected Python type for the parameter.
        default: Default value if the parameter is not provided.
        alias: Optional alias for the parameter.
    """

    name: str
    param_type: str  # "path", "query", "body", "header", "cookie", "file"
    expected_type: type | None = None
    default: Any = None
    alias: str | None = None


@runtime_checkable
class PipeProtocol(Protocol):
    """Transforms or validates a single handler parameter.

    Pipes operate on individual parameters before they reach the handler.
    They can transform (e.g., parse string to int) or validate
    (e.g., check that a value is within range).

    Example:
        ```python
        class ParseIntPipe:
            async def transform(self, value: Any, metadata: ParamMetadata) -> int:
                if value is None:
                    return metadata.default or 0
                try:
                    return int(value)
                except ValueError:
                    raise BadRequestError(f"Invalid integer for {metadata.name}")
        ```
    """

    async def transform(self, value: Any, metadata: ParamMetadata) -> Any:
        """Transform or validate the value.

        Args:
            value: The value to transform/validate.
            metadata: Metadata about the parameter.

        Returns:
            The transformed value.

        Raises:
            Exception: On validation failure (typically HTTP 400 Bad Request).
        """
        ...


def body(
    name: str | None = None,
    *,
    default: Any = ...,
    alias: str | None = None,
) -> ParamMetadata:
    """Create a request-body parameter marker for controller handler methods.

    Returns a ``ParamMetadata`` instance that the web framework recognises as
    a body-binding annotation.  Use it as a default-value sentinel::

        @post("/users")
        async def create_user(self, payload: CreateUserRequest = body()) -> Any:
            ...

    Args:
        name: Optional explicit name override for the parameter.
        default: Default value when the body cannot be parsed.
        alias: Optional deserialization alias.

    Returns:
        A ``ParamMetadata`` configured for ``param_type="body"``.
    """
    return ParamMetadata(
        name=name or "",
        param_type="body",
        default=default,
        alias=alias,
    )


# =============================================================================
# Interceptor Protocols
# =============================================================================
@runtime_checkable
class CallHandlerProtocol(Protocol):
    """Wraps the next step in the pipeline.

    Interceptors use this to continue processing to the next interceptor
    or to the actual handler.
    """

    async def handle(self) -> Any:
        """Continue processing the request.

        Returns the result of the next handler in the pipeline.
        """
        ...


@runtime_checkable
class WebInterceptorProtocol(Protocol):
    """Intercepts request/response flow with full AOP control.

    Interceptors wrap the entire request→handler→response lifecycle,
    enabling cross-cutting concerns like logging, caching, response
    transformation, and timing without modifying handler code.

    Example:
        ```python
        class TimingInterceptor(Interceptor):
            async def intercept(
                self, context: ExecutionContextProtocol, next: CallHandlerProtocol
            ) -> Any:
                start = time.perf_counter()
                result = await next.handle()
                elapsed = time.perf_counter() - start
                return result
        ```
    """

    async def intercept(
        self,
        context: ExecutionContextProtocol,
        next_handler: CallHandlerProtocol,
    ) -> Any:
        """Intercept the request/response flow.

        Args:
            context: Provides metadata about the current request.
            next_handler: Wraps the next step in the pipeline.

        Returns:
            The result of the handler (possibly transformed).

        Notes:
            - MUST call ``await next_handler.handle()`` to continue the pipeline.
            - CAN transform the result before returning.
            - CAN add/modify response headers.
            - CAN short-circuit by returning early without calling next.
        """
        ...


class WebInterceptorBase(WebInterceptorProtocol):
    """Base class for interceptors (optional convenience).

    Provides a no-op implementation that subclasses can override.
    """

    async def intercept(
        self,
        context: ExecutionContextProtocol,
        next_handler: CallHandlerProtocol,
    ) -> Any:
        """Default implementation just passes through."""
        return await next_handler.handle()


# =============================================================================
# Provider Protocols
# =============================================================================


@runtime_checkable
class WebAppAccessorProtocol(Protocol):
    """Provides access to the underlying Starlette application.

    Consumers that only need the Starlette app should depend on this
    protocol instead of the full WebProvider, decoupling from the
    provider's full interface.
    """

    @property
    def starlette(self) -> Any:
        """Return the Starlette application instance.

        Returns:
            The Starlette ASGI application, or None if not yet initialized.
        """
        ...


@runtime_checkable
class ControllerSourceProtocol(Protocol):
    """Provides the list of registered controller classes.

    Consumers that only need access to controllers should depend on this
    protocol instead of the full WebProvider.
    """

    @property
    def controllers(self) -> list[type]:
        """Return the list of registered controller classes.

        Returns:
            A list of controller class types.
        """
        ...


@runtime_checkable
class ConfigAccessorProtocol(Protocol):
    """Provides access to web configuration.

    Consumers that need configuration details should depend on this
    protocol for minimal coupling to the provider.
    """

    @property
    def web_config(self) -> Any:
        """Return the web-layer configuration.

        Returns:
            WebConfig instance with web-layer settings.
        """
        ...

    @property
    def provider_config(self) -> Any:
        """Return the provider-specific configuration.

        Returns:
            WebProviderConfig instance with provider settings.
        """
        ...

    @property
    def debug_routes_auth(self) -> Any:
        """Return the debug routes authentication handler, if set.

        Returns:
            Callable or None.
        """
        ...

    @property
    def fail_on_route_conflict(self) -> bool:
        """Whether to raise on duplicate route registration.

        Returns:
            True if duplicate routes should raise RuntimeError.
        """
        ...


@runtime_checkable
class ProviderResourcesProtocol(Protocol):
    """Provides access to internal provider resources.

    Used by advanced components like routing and middleware managers
    that need direct access to router and OpenAPI generator.
    """

    @property
    def router(self) -> Any:
        """Return the internal Router instance.

        Returns:
            Router instance or None if not initialized.
        """
        ...

    @property
    def openapi_generator(self) -> Any:
        """Return the OpenAPI generator instance.

        Returns:
            OpenAPIGenerator instance or None if not configured.
        """
        ...


@runtime_checkable
class WebProviderProtocol(
    WebAppAccessorProtocol,
    ControllerSourceProtocol,
    ConfigAccessorProtocol,
    ProviderResourcesProtocol,
    Protocol,
):
    """Combined protocol for full WebProvider access.

    This is the complete interface expected by components that need
    the full capabilities of WebProvider. Consumers that need fewer
    properties should depend on the more specific protocols above
    to reduce coupling.
    """


__all__ = [
    # Pipe layer
    "ParamMetadata",
    "PipeProtocol",
    "body",
    # Interceptor layer
    "CallHandlerProtocol",
    "ExecutionContextProtocol",
    "WebInterceptorBase",
    "WebInterceptorProtocol",
    # Provider layer
    "WebAppAccessorProtocol",
    "ControllerSourceProtocol",
    "ConfigAccessorProtocol",
    "ProviderResourcesProtocol",
    "WebProviderProtocol",
]
