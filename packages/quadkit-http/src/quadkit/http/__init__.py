"""HTTP client module for the Quadkit framework.

Provides a first-class async HTTP client, connection pooling, typed request/
response contexts, and a DI provider — available to every application without
pulling in a full web-server framework.

Quick start (standalone, outside DI):

    >>> from quadkit.http import HTTPClient
    >>> async with HTTPClient.session_context() as client:
    ...     response = await client.get("https://api.example.com/health")
    ...     assert response.ok

Quick start (via DI):

    >>> from quadkit.http import HTTPProvider, HTTPClientConfig
    >>> app.add_provider(HTTPProvider(HTTPClientConfig()))
    >>> # Later, resolve from container:
    >>> client = await container.resolve(HTTPClient)

Protocol exports:
    HTTPClientProtocol: Contract for HTTP clients.
    InterceptorProtocol: Contract for HTTP request/response interceptors.
    InterceptorChainProtocol: Contract for interceptor chains.
"""

from __future__ import annotations

from importlib import import_module
import importlib.metadata
from typing import TYPE_CHECKING, Any

__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from quadkit.http.constants import __version__ as __version__

if TYPE_CHECKING:
    from quadkit.http.client import (
        BaseURLHTTPClient as BaseURLHTTPClient,
    )
    from quadkit.http.client import (
        HTTPClient as HTTPClient,
    )
    from quadkit.http.client import (
        StreamContext as StreamContext,
    )
    from quadkit.http.client import (
        StreamResponse as StreamResponse,
    )
    from quadkit.http.config import (
        ConnectionPoolConfig as ConnectionPoolConfig,
    )
    from quadkit.http.config import (
        HTTPClientConfig as HTTPClientConfig,
    )
    from quadkit.http.constants import (
        CONTENT_TYPE_FORM as CONTENT_TYPE_FORM,
    )
    from quadkit.http.constants import (
        CONTENT_TYPE_JSON as CONTENT_TYPE_JSON,
    )
    from quadkit.http.constants import (
        CONTENT_TYPE_TEXT as CONTENT_TYPE_TEXT,
    )
    from quadkit.http.constants import (
        DEFAULT_ENCODING as DEFAULT_ENCODING,
    )
    from quadkit.http.constants import (
        DEFAULT_MAX_CONNECTIONS as DEFAULT_MAX_CONNECTIONS,
    )
    from quadkit.http.constants import (
        DEFAULT_TIMEOUT as DEFAULT_TIMEOUT,
    )
    from quadkit.http.constants import (
        DELETE as DELETE,
    )
    from quadkit.http.constants import (
        GET as GET,
    )
    from quadkit.http.constants import (
        HEAD as HEAD,
    )
    from quadkit.http.constants import (
        OPTIONS as OPTIONS,
    )
    from quadkit.http.constants import (
        PATCH as PATCH,
    )
    from quadkit.http.constants import (
        POST as POST,
    )
    from quadkit.http.constants import (
        PUT as PUT,
    )
    from quadkit.http.di.provider import HTTPProvider
    from quadkit.http.exceptions import (
        HTTPCircuitOpenError as HTTPCircuitOpenError,
    )
    from quadkit.http.exceptions import (
        HTTPClientError as HTTPClientError,
    )
    from quadkit.http.exceptions import (
        HTTPConnectionError as HTTPConnectionError,
    )
    from quadkit.http.exceptions import (
        HTTPInterceptorError as HTTPInterceptorError,
    )
    from quadkit.http.exceptions import (
        HTTPRetryExhaustedError as HTTPRetryExhaustedError,
    )
    from quadkit.http.exceptions import (
        HTTPTimeoutError as HTTPTimeoutError,
    )
    from quadkit.http.lib import (
        build_url as build_url,
    )
    from quadkit.http.lib import (
        extract_json_type as extract_json_type,
    )
    from quadkit.http.lib import (
        format_timeout as format_timeout,
    )
    from quadkit.http.lib import (
        merge_headers as merge_headers,
    )
    from quadkit.http.lib import (
        parse_headers as parse_headers,
    )
    from quadkit.http.lib import (
        parse_url_parts as parse_url_parts,
    )
    from quadkit.http.module import HTTPModule
    from quadkit.http.pool import ConnectionPool
    from quadkit.http.protocols import (
        HTTPClientProtocol as HTTPClientProtocol,
    )
    from quadkit.http.protocols import (
        InterceptorChainProtocol as InterceptorChainProtocol,
    )
    from quadkit.http.protocols import (
        InterceptorProtocol as InterceptorProtocol,
    )
    from quadkit.http.types import (
        RequestContext as RequestContext,
    )
    from quadkit.http.types import (
        ResponseContext as ResponseContext,
    )
    from quadkit.http.validation import (
        validate_host,
        validate_port,
        validate_positive_int,
        validate_public_url,
        validate_timeout,
        validate_url,
    )

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    # Client
    "BaseURLHTTPClient": ("quadkit.http.client", "BaseURLHTTPClient"),
    "HTTPClient": ("quadkit.http.client", "HTTPClient"),
    "StreamContext": ("quadkit.http.client", "StreamContext"),
    "StreamResponse": ("quadkit.http.client", "StreamResponse"),
    # Config
    "ConnectionPoolConfig": ("quadkit.http.config", "ConnectionPoolConfig"),
    "HTTPClientConfig": ("quadkit.http.config", "HTTPClientConfig"),
    # Constants
    "CONTENT_TYPE_JSON": ("quadkit.http.constants", "CONTENT_TYPE_JSON"),
    "CONTENT_TYPE_TEXT": ("quadkit.http.constants", "CONTENT_TYPE_TEXT"),
    "CONTENT_TYPE_FORM": ("quadkit.http.constants", "CONTENT_TYPE_FORM"),
    "DEFAULT_ENCODING": ("quadkit.http.constants", "DEFAULT_ENCODING"),
    "DEFAULT_TIMEOUT": ("quadkit.http.constants", "DEFAULT_TIMEOUT"),
    "GET": ("quadkit.http.constants", "GET"),
    "POST": ("quadkit.http.constants", "POST"),
    "PUT": ("quadkit.http.constants", "PUT"),
    "DELETE": ("quadkit.http.constants", "DELETE"),
    "PATCH": ("quadkit.http.constants", "PATCH"),
    "OPTIONS": ("quadkit.http.constants", "OPTIONS"),
    "HEAD": ("quadkit.http.constants", "HEAD"),
    "DEFAULT_MAX_CONNECTIONS": ("quadkit.http.constants", "DEFAULT_MAX_CONNECTIONS"),
    # Events
    "RequestCompletedEvent": ("quadkit.http.events", "RequestCompletedEvent"),
    "RequestRetryExhaustedEvent": (
        "quadkit.http.events",
        "RequestRetryExhaustedEvent",
    ),
    "RequestTimeoutEvent": ("quadkit.http.events", "RequestTimeoutEvent"),
    # Exceptions
    "HTTPCircuitOpenError": ("quadkit.http.exceptions", "HTTPCircuitOpenError"),
    "HTTPConnectionError": ("quadkit.http.exceptions", "HTTPConnectionError"),
    "HTTPClientError": ("quadkit.http.exceptions", "HTTPClientError"),
    "HTTPInterceptorError": ("quadkit.http.exceptions", "HTTPInterceptorError"),
    "HTTPRetryExhaustedError": ("quadkit.http.exceptions", "HTTPRetryExhaustedError"),
    "HTTPTimeoutError": ("quadkit.http.exceptions", "HTTPTimeoutError"),
    # Protocols
    "HTTPClientProtocol": ("quadkit.http.protocols", "HTTPClientProtocol"),
    "InterceptorProtocol": ("quadkit.http.protocols", "InterceptorProtocol"),
    "InterceptorChainProtocol": ("quadkit.http.protocols", "InterceptorChainProtocol"),
    # Utils (URL, header, format helpers)
    "build_url": ("quadkit.http.lib", "build_url"),
    "extract_json_type": ("quadkit.http.lib", "extract_json_type"),
    "format_timeout": ("quadkit.http.lib", "format_timeout"),
    "merge_headers": ("quadkit.http.lib", "merge_headers"),
    "parse_headers": ("quadkit.http.lib", "parse_headers"),
    "parse_url_parts": ("quadkit.http.lib", "parse_url_parts"),
    # Pool
    "ConnectionPool": ("quadkit.http.pool", "ConnectionPool"),
    # Provider
    "HTTPModule": ("quadkit.http.module", "HTTPModule"),
    "HTTPProvider": ("quadkit.http.di.provider", "HTTPProvider"),
    # Types
    "RequestContext": ("quadkit.http.types", "RequestContext"),
    "ResponseContext": ("quadkit.http.types", "ResponseContext"),
    # Outbound WebSocket transport
    "WebSocketClient": ("quadkit.http.websocket", "WebSocketClient"),
    "WebSocketMessage": ("quadkit.http.websocket", "WebSocketMessage"),
    # Validation
    "validate_host": ("quadkit.http.validation", "validate_host"),
    "validate_port": ("quadkit.http.validation", "validate_port"),
    "validate_positive_int": ("quadkit.http.validation", "validate_positive_int"),
    "validate_public_url": ("quadkit.http.validation", "validate_public_url"),
    "validate_timeout": ("quadkit.http.validation", "validate_timeout"),
    "validate_url": ("quadkit.http.validation", "validate_url"),
    # Hooks
    "HTTPRequestSentHook": ("quadkit.http.hooks", "HTTPRequestSentHook"),
    "HTTPResponseReceivedHook": ("quadkit.http.hooks", "HTTPResponseReceivedHook"),
}


def __getattr__(name: str) -> Any:
    """Lazy-load attributes to keep import time low."""
    if name in _LAZY_IMPORTS:
        module_path, attr_name = _LAZY_IMPORTS[name]
        module = import_module(module_path)
        value = getattr(module, attr_name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    """Expose lazy names for IDE completion."""
    return sorted(set(__all__) | set(_LAZY_IMPORTS.keys()))


__all__ = list(_LAZY_IMPORTS)
