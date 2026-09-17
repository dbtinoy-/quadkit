"""Security headers middleware for web applications.

Implements OWASP recommended security headers to protect against common vulnerabilities.
Consumes SecurityConfig directly from application.yaml structure.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.logging import get_logger
from quadkit.web.security.config import (
    CrossOriginConfig,
    CSPConfig,
    CSRFConfig,
    HSTSConfig,
    SecurityConfig,
)
from quadkit.web.security.sanitization import HeaderSanitizer

logger = get_logger(__name__)

_header_sanitizer = HeaderSanitizer()


if TYPE_CHECKING:
    from starlette.types import ASGIApp, Receive, Scope, Send


class SecurityHeadersMiddleware:
    """Middleware to add security headers to all responses.

    Implements OWASP security best practices for HTTP headers.
    Consumes SecurityConfig directly from application.yaml.

    Usage:
        from quadkit.web.middleware.security import SecurityHeadersMiddleware
        from quadkit.web.security.config import SecurityConfig

        config = SecurityConfig(...)
        app.add_middleware(SecurityHeadersMiddleware, config=config)
    """

    def __init__(
        self,
        app: ASGIApp,
        config: SecurityConfig | None = None,
        enabled: bool = True,
    ):
        """Initialize security headers middleware.

        Args:
            app: ASGI application
            config: SecurityConfig from application.yaml
            enabled: Whether middleware is enabled
        """
        self.app = app
        self.enabled = enabled

        self.config = config or SecurityConfig()

        if enabled:
            logger.info("Security headers middleware enabled")
            if self.config.hsts.enabled:
                logger.info("HSTS enabled - ensure HTTPS is configured")
        else:
            logger.warning("Security headers middleware disabled")

    def _build_csp_header(self) -> str:
        """Build Content-Security-Policy header value from directives."""
        if not self.config.csp.enabled:
            return ""
        return self.config.csp.build_header()

    def _build_hsts_header(self) -> str:
        """Build Strict-Transport-Security header value."""
        parts = [f"max-age={self.config.hsts.max_age}"]
        if self.config.hsts.include_subdomains:
            parts.append("includeSubDomains")
        if self.config.hsts.preload:
            parts.append("preload")
        return "; ".join(parts)

    def _build_permissions_policy_header(self) -> str:
        """Build Permissions-Policy header value."""
        policies = []
        for feature, allowlist in self.config.permissions_policy.items():
            policies.append(f"{feature}={allowlist}")
        return ", ".join(policies)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Add security headers to response."""
        if scope["type"] != "http" or not self.enabled:
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message: Any) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))

                # Content-Security-Policy
                if self.config.csp.enabled and self.config.csp.directives:
                    csp = self._build_csp_header()
                    if csp:
                        headers.append((b"content-security-policy", csp.encode()))

                # Custom headers from config dict — sanitize values before encoding
                # to prevent CRLF injection / response-splitting attacks.
                for header_name, header_value in self.config.custom_headers.items():
                    name = header_name.lower().encode()
                    safe_value = _header_sanitizer.sanitize_header_value(
                        str(header_value)
                    )
                    headers.append((name, safe_value.encode()))

                # Strict-Transport-Security (only in production with HTTPS)
                if self.config.hsts.enabled:
                    hsts = self._build_hsts_header()
                    headers.append((b"strict-transport-security", hsts.encode()))

                # Referrer-Policy (use referrer_policy field if not already in custom_headers)
                if (
                    self.config.referrer_policy
                    and "referrer-policy" not in self.config.custom_headers
                ):
                    headers.append(
                        (b"referrer-policy", self.config.referrer_policy.encode()),
                    )

                # Permissions-Policy
                if self.config.permissions_policy:
                    policy = self._build_permissions_policy_header()
                    headers.append((b"permissions-policy", policy.encode()))

                # Cross-Origin policies
                if self.config.cross_origin.enabled:
                    headers.append(
                        (
                            b"cross-origin-embedder-policy",
                            self.config.cross_origin.embedder_policy.encode(),
                        ),
                    )
                    headers.append(
                        (
                            b"cross-origin-opener-policy",
                            self.config.cross_origin.opener_policy.encode(),
                        ),
                    )
                    headers.append(
                        (
                            b"cross-origin-resource-policy",
                            self.config.cross_origin.resource_policy.encode(),
                        ),
                    )

                message["headers"] = headers

            await send(message)

        await self.app(scope, receive, send_wrapper)


class DocsCSPMiddleware:
    """Route-scoped Content-Security-Policy for the API docs pages.

    plans/09172026 H-03: the vendored docs UIs (Swagger UI, ReDoc) run under
    a strict ``'self'``-only policy — no ``unsafe-inline``/``unsafe-eval``,
    no third-party CDNs, ``connect-src 'self'`` — applied to the docs HTML
    pages and their assets. Other routes keep whatever policy the
    application configures (``web.security.csp``), so this never loosens or
    constrains user-served pages.

    Args:
        app: The wrapped ASGI application.
        docs_paths: URL prefixes the policy applies to (e.g. ``/docs``,
            ``/redoc``, ``/docs-static``).
        policy: The serialized CSP header value.
    """

    def __init__(
        self,
        app: Any,
        docs_paths: tuple[str, ...],
        policy: str,
    ) -> None:
        self.app = app
        self._docs_paths = tuple(p.rstrip("/") + "/" for p in docs_paths if p)
        # exact matches too ("/docs" without trailing slash)
        self._exact = tuple(p.rstrip("/") for p in docs_paths if p)
        self._policy = policy

    def _is_docs_path(self, path: str) -> bool:
        if path in self._exact:
            return True
        return any(path.startswith(prefix) for prefix in self._docs_paths)

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        """Wrap send to attach the docs CSP header on matching responses."""
        if scope.get("type") != "http" or not self._is_docs_path(scope.get("path", "")):
            await self.app(scope, receive, send)
            return

        async def send_with_csp(message: Any) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append([b"content-security-policy", self._policy.encode()])
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_csp)


def create_security_middleware(
    config: SecurityConfig,
    enabled: bool = True,
) -> dict[str, Any]:
    """Factory to create SecurityHeadersMiddleware kwargs from SecurityConfig.

    Returns kwargs dict suitable for Starlette's Middleware class:
        Middleware(SecurityHeadersMiddleware, **kwargs)
    """
    return {
        "config": config,
        "enabled": enabled,
    }


def create_development_config() -> SecurityConfig:
    """Create security headers config for development.

    More permissive CSP and disables HSTS.
    """
    return SecurityConfig(
        hsts=HSTSConfig(enabled=False),
        csp=CSPConfig(
            enabled=True,
            directives={
                "default-src": "'self'",
                "script-src": "'self' 'unsafe-inline' 'unsafe-eval' http://localhost:*",
                "script-src-elem": "'self' 'unsafe-inline' 'unsafe-eval' http://localhost:*",
                "style-src": "'self' 'unsafe-inline' http://localhost:*",
                "img-src": "'self' data: http: https: blob:",
                "font-src": "'self' data: http://localhost:*",
                "connect-src": "'self' http://localhost:* ws://localhost:* wss://localhost:*",
                "frame-ancestors": "'self' http://localhost:*",
            },
        ),
        cross_origin=CrossOriginConfig(enabled=False),
    )


def create_production_config() -> SecurityConfig:
    """Create security headers config optimized for production.

    More restrictive CSP, enables HSTS and CSRF.
    """
    return SecurityConfig(
        hsts=HSTSConfig(
            enabled=True,
            max_age=31536000,
            include_subdomains=True,
            preload=False,
        ),
        csp=CSPConfig(
            enabled=True,
            directives={
                "default-src": "'self'",
                "script-src": "'self'",
                "script-src-elem": "'self'",
                "style-src": "'self'",
                "img-src": "'self' https: data: blob:",
                "font-src": "'self' data:",
                "connect-src": "'self' wss: https:",
                "frame-ancestors": "'none'",
                "base-uri": "'self'",
                "form-action": "'self'",
                "upgrade-insecure-requests": "",
            },
        ),
        cross_origin=CrossOriginConfig(enabled=True),
        csrf=CSRFConfig(enabled=True),
    )


__all__ = [
    "SecurityHeadersMiddleware",
    "create_development_config",
    "create_production_config",
    "create_security_middleware",
]
