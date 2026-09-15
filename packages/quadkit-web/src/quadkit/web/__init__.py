"""Quadkit Web - Progressive Web Framework for Quadkit"""

from __future__ import annotations

import importlib.metadata
from typing import TYPE_CHECKING, Any

__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from quadkit.web.constants import __version__ as __version__

if TYPE_CHECKING:
    from quadkit.web.config import WebConfig
    from quadkit.web.di.provider import WebProvider
    from quadkit.web.di.rate_limit import RateLimitProvider


# =============================================================================
# Lazy Loading to Avoid Circular Imports
# =============================================================================

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    # Discovery
    "discover_controllers": ("quadkit.web.routing.discovery", "discover_controllers"),
    "discover_websocket_handlers": (
        "quadkit.web.routing.discovery",
        "discover_websocket_handlers",
    ),
    # Config & Provider
    "WebConfig": ("quadkit.web.config", "WebConfig"),
    "WebProvider": ("quadkit.web.di.provider", "WebProvider"),
    "RateLimitProvider": ("quadkit.web.di.rate_limit", "RateLimitProvider"),
    # Modules
    "WebModule": ("quadkit.web.module", "WebModule"),
    # Routing
    "Controller": ("quadkit.web.routing.controllers", "Controller"),
    "CQRSController": ("quadkit.web.routing.cqrs", "CQRSController"),
    "ControllerRegistry": (
        "quadkit.web.routing.controller_registry",
        "ControllerRegistry",
    ),
    "GenericController": ("quadkit.web.routing.controller", "GenericController"),
    "Router": ("quadkit.web.routing.router", "Router"),
    "RouteRegistry": ("quadkit.web.routing.registry", "RouteRegistry"),
    "VersionExtractor": ("quadkit.web.routing.versioning", "VersionExtractor"),
    "ApiVersionMetadata": ("quadkit.web.routing.versioning", "ApiVersionMetadata"),
    "api_version": ("quadkit.web.routing.versioning", "api_version"),
    # Parameters
    "body": ("quadkit.web.routing.parameters", "body"),
    "controller": ("quadkit.web.routing.controller_registry", "controller"),
    "controller_registry": (
        "quadkit.web.routing.controller_registry",
        "controller_registry",
    ),
    "cookie": ("quadkit.web.routing.parameters", "cookie"),
    "file": ("quadkit.web.routing.parameters", "file"),
    "form": ("quadkit.web.routing.parameters", "form"),
    "get_version": ("quadkit.web.routing.versioning", "get_version"),
    "header": ("quadkit.web.routing.parameters", "header"),
    "path": ("quadkit.web.routing.parameters", "path"),
    "query": ("quadkit.web.routing.parameters", "query"),
    "register_controller": ("quadkit.web.routing.registry", "register_controller"),
    "route_registry": ("quadkit.web.routing.registry", "route_registry"),
    "version": ("quadkit.web.routing.versioning", "version"),
    # HTTP Methods (from decorators)
    "delete": ("quadkit.web.routing.decorators", "delete"),
    "get": ("quadkit.web.routing.decorators", "get"),
    "head": ("quadkit.web.routing.decorators", "head"),
    "options": ("quadkit.web.routing.decorators", "options"),
    "patch": ("quadkit.web.routing.decorators", "patch"),
    "post": ("quadkit.web.routing.decorators", "post"),
    "put": ("quadkit.web.routing.decorators", "put"),
    "trace": ("quadkit.web.routing.decorators", "trace"),
    "websocket": ("quadkit.web.routing.decorators", "websocket"),
    "websocket_handler": ("quadkit.web.websocket.decorators", "websocket_handler"),
    # Transport
    "Response": ("quadkit.web.transport.responses", "Response"),
    "FastJSONResponse": ("quadkit.web.transport.responses", "FastJSONResponse"),
    "HTMXResponse": ("quadkit.web.transport.responses", "HTMXResponse"),
    "HTMLContent": ("quadkit.web.transport.responses", "HTMLContent"),
    "JSONResponse": ("quadkit.web.transport.responses", "JSONResponse"),
    "HTMLResponse": ("quadkit.web.transport.responses", "HTMLResponse"),
    "RedirectResponse": ("quadkit.web.transport.responses", "RedirectResponse"),
    "StreamingResponse": ("quadkit.web.transport.responses", "StreamingResponse"),
    "FileResponse": ("quadkit.web.transport.responses", "FileResponse"),
    "WebSocket": ("quadkit.web.transport.websockets", "WebSocket"),
    # Template rendering
    "render_template": ("quadkit.web.templates.core", "render_template"),
    # Response helpers
    "json_response": ("quadkit.web.transport.responses", "json_response"),
    "html_response": ("quadkit.web.transport.responses", "html_response"),
    "redirect_response": ("quadkit.web.transport.responses", "redirect_response"),
    "streaming_response": ("quadkit.web.transport.responses", "streaming_response"),
    "file_response": ("quadkit.web.transport.responses", "file_response"),
    # Middleware
    "DefaultMiddlewareStack": (
        "quadkit.web.middleware.stack",
        "DefaultMiddlewareStack",
    ),
    "InputSanitizationMiddleware": (
        "quadkit.web.middleware.sanitization",
        "InputSanitizationMiddleware",
    ),
    # Security
    "RoleGuard": ("quadkit.web.security.guards", "RoleGuard"),
    "guard": ("quadkit.web.security.shortcuts", "guard"),
    "roles": ("quadkit.web.security.shortcuts", "roles"),
    # Exceptions
    "HTTPError": ("quadkit.web.exceptions", "HTTPError"),
    "NotFoundError": ("quadkit.web.exceptions", "NotFoundError"),
    "ConflictError": ("quadkit.web.exceptions", "ConflictError"),
    "RateLimitError": ("quadkit.web.exceptions", "RateLimitError"),
    "TooManyConnectionsError": ("quadkit.web.exceptions", "TooManyConnectionsError"),
    "InternalServerError": ("quadkit.web.exceptions", "InternalServerError"),
    # Background tasks
    "background": ("quadkit.web.background.decorator", "background"),
    "BackgroundTasks": ("quadkit.web.background.tasks", "BackgroundTasks"),
    # Errors
    "ProblemDetail": ("quadkit.web.errors.problem_detail", "ProblemDetail"),
    # Request state helpers
    "get_request_id": ("quadkit.web.dependencies.functions", "get_request_id"),
    "get_current_user_optional": (
        "quadkit.web.dependencies.functions",
        "get_current_user_optional",
    ),
    "get_current_user_required": (
        "quadkit.web.dependencies.functions",
        "get_current_user_required",
    ),
    # Rate limiting sugar
    "throttle": ("quadkit.web.integrations.throttle", "throttle"),
    "RateLimitModule": ("quadkit.web.integrations.throttle", "RateLimitModule"),
    # Quickstart
    "app": ("quadkit.web.quickstart", "app"),
    # DI decorators — quickstart-aware versions that also register in the
    # quickstart service registry so classes defined in any scope are discovered.
    "singleton": ("quadkit.web.quickstart", "singleton"),
    "injectable": ("quadkit.web.quickstart", "injectable"),
    "transient": ("quadkit.di", "transient"),
    # Result bridge
    "ResultResponseMapper": (
        "quadkit.web.routing.result_bridge",
        "ResultResponseMapper",
    ),
    "error_status": ("quadkit.web.routing.result_bridge", "error_status"),
    # Protocols (web-layer pipe + interceptor)
    "ParamMetadata": ("quadkit.web.protocols", "ParamMetadata"),
    "PipeProtocol": ("quadkit.web.protocols", "PipeProtocol"),
    "ExecutionContextProtocol": ("quadkit.web.protocols", "ExecutionContextProtocol"),
    "CallHandlerProtocol": ("quadkit.web.protocols", "CallHandlerProtocol"),
    "WebInterceptorProtocol": ("quadkit.web.protocols", "WebInterceptorProtocol"),
    "WebInterceptorBase": ("quadkit.web.protocols", "WebInterceptorBase"),
    # Provider protocols (decoupling)
    "WebAppAccessorProtocol": ("quadkit.web.protocols", "WebAppAccessorProtocol"),
    "ControllerSourceProtocol": ("quadkit.web.protocols", "ControllerSourceProtocol"),
    "ConfigAccessorProtocol": ("quadkit.web.protocols", "ConfigAccessorProtocol"),
    "ProviderResourcesProtocol": (
        "quadkit.web.protocols",
        "ProviderResourcesProtocol",
    ),
    "WebProviderProtocol": ("quadkit.web.protocols", "WebProviderProtocol"),
    # Hooks
    "WebRequestReceivedHook": ("quadkit.web.hooks", "WebRequestReceivedHook"),
    "WebResponsePreparedHook": ("quadkit.web.hooks", "WebResponsePreparedHook"),
    "WebServerStartedHook": ("quadkit.web.hooks", "WebServerStartedHook"),
    "WebServerStoppedHook": ("quadkit.web.hooks", "WebServerStoppedHook"),
    # Core re-exports
    "Result": ("quadkit.result", "Result"),
    "Ok": ("quadkit.result", "Ok"),
    "Err": ("quadkit.result", "Err"),
}


def __getattr__(name: str) -> Any:
    """Lazy load attributes to avoid circular imports."""
    if name in _LAZY_IMPORTS:
        import importlib

        module_path, attr_name = _LAZY_IMPORTS[name]
        module = importlib.import_module(module_path)
        value = getattr(module, attr_name)
        # Cache in module globals so __getattr__ isn't called again for this name
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    """List available attributes for IDE support (deduplicated, sorted).

    ``__all__`` already mirrors the lazy map, so the previous
    ``list(__all__) + list(_LAZY_IMPORTS.keys())`` listed every public name
    twice.
    """
    return sorted(set(globals()) | set(_LAZY_IMPORTS) | {"__version__"})


# Curated, sorted export list (kept in sync with _LAZY_IMPORTS) so tooling
# and docs see a stable ordering rather than the lazy map's insertion order.
__all__ = [
    "ApiVersionMetadata",
    "BackgroundTasks",
    "CQRSController",
    "CallHandlerProtocol",
    "ConfigAccessorProtocol",
    "ConflictError",
    "Controller",
    "ControllerRegistry",
    "ControllerSourceProtocol",
    "DefaultMiddlewareStack",
    "Err",
    "ExecutionContextProtocol",
    "FastJSONResponse",
    "FileResponse",
    "GenericController",
    "HTMLContent",
    "HTMLResponse",
    "HTMXResponse",
    "HTTPError",
    "InputSanitizationMiddleware",
    "InternalServerError",
    "JSONResponse",
    "NotFoundError",
    "Ok",
    "ParamMetadata",
    "PipeProtocol",
    "ProblemDetail",
    "ProviderResourcesProtocol",
    "RateLimitError",
    "RateLimitModule",
    "RateLimitProvider",
    "RedirectResponse",
    "Response",
    "Result",
    "ResultResponseMapper",
    "RoleGuard",
    "RouteRegistry",
    "Router",
    "StreamingResponse",
    "TooManyConnectionsError",
    "VersionExtractor",
    "WebAppAccessorProtocol",
    "WebConfig",
    "WebInterceptorBase",
    "WebInterceptorProtocol",
    "WebModule",
    "WebProvider",
    "WebProviderProtocol",
    "WebRequestReceivedHook",
    "WebResponsePreparedHook",
    "WebServerStartedHook",
    "WebServerStoppedHook",
    "WebSocket",
    "api_version",
    "app",
    "background",
    "body",
    "controller",
    "controller_registry",
    "cookie",
    "delete",
    "discover_controllers",
    "discover_websocket_handlers",
    "error_status",
    "file",
    "file_response",
    "form",
    "get",
    "get_current_user_optional",
    "get_current_user_required",
    "get_request_id",
    "get_version",
    "guard",
    "head",
    "header",
    "html_response",
    "injectable",
    "json_response",
    "options",
    "patch",
    "path",
    "post",
    "put",
    "query",
    "redirect_response",
    "register_controller",
    "render_template",
    "roles",
    "route_registry",
    "singleton",
    "streaming_response",
    "throttle",
    "trace",
    "transient",
    "version",
    "websocket",
    "websocket_handler",
]
