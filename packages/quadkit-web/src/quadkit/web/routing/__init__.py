from __future__ import annotations

from typing import Any

from quadkit.web.routing.controller import GenericController
from quadkit.web.routing.controller_registry import (
    ControllerRegistry,
    controller,
)
from quadkit.web.routing.controllers import Controller
from quadkit.web.routing.cqrs import CQRSController
from quadkit.web.routing.decorators import (
    delete,
    get,
    head,
    options,
    patch,
    post,
    put,
    trace,
    websocket,
)
from quadkit.web.routing.discovery import (
    discover_controllers,
    discover_websocket_handlers,
)


def __dir__() -> list[str]:
    return sorted(__all__)


from quadkit.web.routing.execution_context import WebExecutionContext
from quadkit.web.routing.parameter_binder import ParameterBinder
from quadkit.web.routing.parameters import (
    body,
    cookie,
    file,
    form,
    header,
    path,
    query,
)
from quadkit.web.routing.pipeline import RequestPipeline
from quadkit.web.routing.registry import (
    RouteRegistry,
    register_controller,
)
from quadkit.web.routing.router import Router
from quadkit.web.routing.versioning import (
    ApiVersionMetadata,
    VersionExtractor,
    VersioningMiddleware,
    VersioningStrategy,
    api_version,
    get_version,
    version,
)


def __getattr__(name: str) -> Any:
    if name == "VersioningConfig":
        from quadkit.web.routing.versioning import VersioningConfig

        return VersioningConfig
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "ApiVersionMetadata",
    "CQRSController",
    "Controller",
    "ControllerRegistry",
    "GenericController",
    "ParameterBinder",
    "RequestPipeline",
    "RouteRegistry",
    "Router",
    "VersionExtractor",
    "VersioningConfig",
    "VersioningMiddleware",
    "VersioningStrategy",
    "WebExecutionContext",
    "api_version",
    "body",
    "controller",
    "cookie",
    "delete",
    "discover_controllers",
    "discover_websocket_handlers",
    "file",
    "form",
    "get",
    "get_version",
    "head",
    "header",
    "options",
    "patch",
    "path",
    "post",
    "put",
    "query",
    "register_controller",
    "trace",
    "version",
    "websocket",
]
