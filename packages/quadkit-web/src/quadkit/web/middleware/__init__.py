"""Middleware Domain - Web-Specific Middleware"""

from __future__ import annotations

from quadkit.web.middleware.access_log import AccessLogMiddleware
from quadkit.web.middleware.auth import (
    AuthenticationError,
    AuthenticationMiddleware,
    AuthenticatorProtocol,
    AuthorizationError,
    AuthorizerProtocol,
)
from quadkit.web.middleware.base import (
    MiddlewareChain,
    MiddlewareRegistry,
)
from quadkit.web.middleware.body_limit import RequestBodySizeLimitMiddleware
from quadkit.web.middleware.compression import CompressionMiddleware
from quadkit.web.middleware.cors import (
    CORSMiddleware,
    create_development_cors,
    create_production_cors,
)
from quadkit.web.middleware.rate_limit import (
    RateLimiter,
    RateLimitMiddleware,
    rate_limit,
)
from quadkit.web.middleware.request_context import RequestContextMiddleware
from quadkit.web.middleware.request_id import (
    RequestIDLogFilter,
    configure_logging_with_request_id,
)
from quadkit.web.middleware.role_guard import (
    RoleGuardMiddleware,
    RoleGuardRule,
    RoleResolverProtocol,
)
from quadkit.web.middleware.sanitization import InputSanitizationMiddleware
from quadkit.web.middleware.security import (
    SecurityHeadersMiddleware,
    create_development_config,
    create_production_config,
    create_security_middleware,
)
from quadkit.web.middleware.stack import DefaultMiddlewareStack
from quadkit.web.middleware.static import StaticFileProvider, StaticFilesMiddleware
from quadkit.web.middleware.timing import TimingMiddleware

__all__ = [
    # Access logging
    "AccessLogMiddleware",
    # Exceptions
    "AuthenticationError",
    # Authentication middleware (transport layer only)
    "AuthenticationMiddleware",
    # Protocols for authentication
    "AuthenticatorProtocol",
    "AuthorizationError",
    "AuthorizerProtocol",
    "CORSMiddleware",
    # HTTP middleware
    "CompressionMiddleware",
    # Default stack
    "DefaultMiddlewareStack",
    # Input sanitization
    "InputSanitizationMiddleware",
    "MiddlewareChain",
    "MiddlewareRegistry",
    "RateLimitMiddleware",
    "RateLimiter",
    # Body size protection
    "RequestBodySizeLimitMiddleware",
    "RequestContextMiddleware",
    "RequestIDLogFilter",
    # Role guard
    "RoleGuardMiddleware",
    "RoleGuardRule",
    "RoleResolverProtocol",
    # Security headers middleware
    "SecurityHeadersMiddleware",
    "StaticFileProvider",
    "StaticFilesMiddleware",
    "TimingMiddleware",
    "configure_logging_with_request_id",
    "create_development_config",
    "create_development_cors",
    "create_production_config",
    "create_production_cors",
    "create_security_middleware",
    "rate_limit",
]
