"""Web Framework Types and Data Structures

This module defines the core types, enums, and data structures used throughout
the Quadkit Web framework. These provide type safety and consistent interfaces.
"""

from __future__ import annotations

from abc import ABC
from enum import IntEnum, StrEnum
from typing import Any

from quadkit.web.config import ServerConfig, WebProviderConfig

# Re-export key types from submodules
from quadkit.web.protocols import ParamMetadata
from quadkit.web.routing.versioning import VersioningConfig, VersioningStrategy


# HTTP Method enum for type safety
class HTTPMethod(StrEnum):
    """HTTP methods supported by the framework"""

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"
    TRACE = "TRACE"


# Content type constants
class ContentType(StrEnum):
    """Common content types"""

    JSON = "application/json"
    FORM = "application/x-www-form-urlencoded"
    MULTIPART = "multipart/form-data"
    TEXT = "text/plain"
    HTML = "text/html"
    XML = "application/xml"


# Status code groups for convenience
class StatusCode(IntEnum):
    """HTTP status code constants"""

    # 2xx Success
    OK = 200
    CREATED = 201
    ACCEPTED = 202
    NO_CONTENT = 204

    # 3xx Redirection
    MOVED_PERMANENTLY = 301
    FOUND = 302
    NOT_MODIFIED = 304

    # 4xx Client Error
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    METHOD_NOT_ALLOWED = 405
    CONFLICT = 409
    UNPROCESSABLE_ENTITY = 422
    TOO_MANY_REQUESTS = 429

    # 5xx Server Error
    INTERNAL_SERVER_ERROR = 500
    NOT_IMPLEMENTED = 501
    BAD_GATEWAY = 502
    SERVICE_UNAVAILABLE = 503
    GATEWAY_TIMEOUT = 504


class PipeBase(ABC):
    """Base class for pipes (optional convenience).

    Provides a no-op implementation that subclasses can override.
    """

    async def transform(self, value: Any, metadata: ParamMetadata) -> Any:
        """Default implementation just returns the value."""
        return value


__all__ = [
    # HTTP types
    "ContentType",
    "HTTPMethod",
    "ParamMetadata",
    "PipeBase",
    # Configuration types
    "ServerConfig",
    "StatusCode",
    # Versioning types
    "VersioningConfig",
    "VersioningStrategy",
    "WebProviderConfig",
]
