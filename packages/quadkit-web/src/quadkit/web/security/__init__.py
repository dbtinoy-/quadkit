"""HTTP security public API for Quadkit Web."""

from __future__ import annotations

from quadkit.web.middleware.security import SecurityHeadersMiddleware
from quadkit.web.security.config import (
    CORSConfig,
    CrossOriginConfig,
    CSPConfig,
    CSRFConfig,
    HSTSConfig,
    SecurityConfig,
    SecurityHeadersConfig,
)
from quadkit.web.security.context import SecurityContext, get_security_context
from quadkit.web.security.cors.middleware import CORSMiddleware, CORSMiddlewareFactory
from quadkit.web.security.csp.builder import CSPPolicy
from quadkit.web.security.csrf.middleware import CSRFProtectionMiddleware
from quadkit.web.security.guards import (
    AuthGuard,
    GuardProtocol,
    PermissionGuard,
    RoleGuard,
    use_guards,
)

__all__ = [
    "AuthGuard",
    "CORSConfig",
    "CORSMiddleware",
    "CORSMiddlewareFactory",
    "CSPConfig",
    "CSPPolicy",
    "CSRFConfig",
    "CSRFProtectionMiddleware",
    "CrossOriginConfig",
    "GuardProtocol",
    "HSTSConfig",
    "PermissionGuard",
    "RoleGuard",
    "SecurityConfig",
    "SecurityContext",
    "SecurityHeadersConfig",
    "SecurityHeadersMiddleware",
    "get_security_context",
    "use_guards",
]
