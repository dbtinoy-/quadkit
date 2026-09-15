"""CORS middleware for ASGI applications.

Implements Cross-Origin Resource Sharing (CORS) per the WHATWG CORS spec,
using configuration from :class:`~quadkit.web.security.config.CORSConfig`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.logging import get_logger
from quadkit.web.security.config import CORSConfig

if TYPE_CHECKING:
    from collections.abc import Callable

logger = get_logger(__name__)

_SIMPLE_METHODS = {"GET", "HEAD", "POST"}
_SIMPLE_HEADERS = {
    "accept",
    "accept-language",
    "content-language",
    "content-type",
}


class CORSMiddleware:
    """ASGI middleware for Cross-Origin Resource Sharing (CORS).

    Handles preflight requests, adds CORS headers to responses, and enforces
    origin allowlist and credential policies per CORS specification.

    Attributes:
        app: The wrapped ASGI application.
        config: CORS configuration.
    """

    def __init__(self, app: Callable[..., Any], config: CORSConfig) -> None:
        """Initialize middleware.

        Args:
            app: ASGI application to wrap.
            config: CORS configuration.
        """
        self.app = app
        self.config = config
        self._preflight_headers: dict[str, str] = {}
        self._build_preflight_headers()

    def _build_preflight_headers(self) -> None:
        """Pre-compute preflight response headers."""
        methods_str = ", ".join(sorted(self.config.allow_methods))
        headers_str = (
            ", ".join(sorted(self.config.allow_headers))
            if self.config.allow_headers != ["*"]
            else "*"
        )

        self._preflight_headers = {
            "Access-Control-Allow-Methods": methods_str,
            "Access-Control-Allow-Headers": headers_str,
        }

        if self.config.expose_headers:
            self._preflight_headers["Access-Control-Expose-Headers"] = ", ".join(
                self.config.expose_headers
            )

        if self.config.max_age:
            self._preflight_headers["Access-Control-Max-Age"] = str(self.config.max_age)

    def _is_origin_allowed(self, origin: str) -> bool:
        """Check if origin is in allow-list (case-insensitive).

        Args:
            origin: Request origin.

        Returns:
            True if origin is allowed, False otherwise.
        """
        if not origin:
            return False

        if "*" in self.config.allowed_origins:
            return True

        origin_lower = origin.lower()
        return any(o.lower() == origin_lower for o in self.config.allowed_origins)

    def _get_cors_headers(self, origin: str | None) -> dict[str, str]:
        """Compute CORS response headers for a request.

        Args:
            origin: Request origin.

        Returns:
            Dictionary of CORS headers to add to response.
        """
        headers: dict[str, str] = {}

        if not origin or not self._is_origin_allowed(origin):
            return headers

        if "*" in self.config.allowed_origins:
            if self.config.allow_credentials:
                headers["Access-Control-Allow-Origin"] = origin
            else:
                headers["Access-Control-Allow-Origin"] = "*"
        else:
            headers["Access-Control-Allow-Origin"] = origin

        if self.config.allow_credentials:
            headers["Access-Control-Allow-Credentials"] = "true"

        if self.config.expose_headers:
            headers["Access-Control-Expose-Headers"] = ", ".join(
                self.config.expose_headers
            )

        # Vary: Origin required when the response differs by origin (not wildcard).
        # Without it, shared caches may serve a CORS-enabled response to a different
        # origin that should not receive CORS headers — a cache-poisoning risk.
        if headers.get("Access-Control-Allow-Origin") != "*":
            headers["Vary"] = "Origin"

        return headers

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Callable[..., Any],
        send: Callable[..., Any],
    ) -> None:
        """ASGI middleware entry point.

        Args:
            scope: ASGI scope.
            receive: ASGI receive callable.
            send: ASGI send callable.
        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {k.lower(): v for k, v in scope.get("headers", [])}
        origin_bytes = headers.get(b"origin")
        origin = origin_bytes.decode("latin-1") if origin_bytes else None
        method = scope.get("method", "GET")

        # Handle preflight requests
        if method == "OPTIONS" and origin:
            cors_headers = self._get_cors_headers(origin)
            if cors_headers:
                # Validate Access-Control-Request-Headers against allowlist.
                requested_headers_raw = headers.get(
                    b"access-control-request-headers", b""
                ).decode()
                if requested_headers_raw:
                    requested = {
                        h.strip().lower() for h in requested_headers_raw.split(",")
                    }
                    if "*" not in self.config.allow_headers:
                        allowed = {h.lower() for h in self.config.allow_headers}
                        if not requested.issubset(allowed):
                            logger.warning(
                                "cors_preflight_rejected_headers",
                                origin=origin,
                                requested=sorted(requested),
                                allowed=sorted(allowed),
                            )
                            await send(
                                {
                                    "type": "http.response.start",
                                    "status": 403,
                                    "headers": [],
                                }
                            )
                            await send(
                                {
                                    "type": "http.response.body",
                                    "body": b"",
                                    "more_body": False,
                                }
                            )
                            return

                all_headers = {**self._preflight_headers, **cors_headers}
                await send(
                    {
                        "type": "http.response.start",
                        "status": 204,
                        "headers": [
                            (k.encode(), v.encode()) for k, v in all_headers.items()
                        ],
                    }
                )
                await send({"type": "http.response.body", "body": b""})
                return

        # Wrap send to add CORS headers to actual response
        async def send_with_cors(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.start" and origin:
                cors_headers = self._get_cors_headers(origin)
                if cors_headers:
                    headers_list = list(message.get("headers", []))
                    for k, v in cors_headers.items():
                        headers_list.append((k.encode(), v.encode()))
                    message["headers"] = headers_list

            await send(message)

        await self.app(scope, receive, send_with_cors)


class CORSMiddlewareFactory:
    """Factory that builds configured :class:`CORSMiddleware` instances."""

    def __init__(self, config: CORSConfig | None = None) -> None:
        self._config = config or CORSConfig()

    def __call__(
        self,
        app: Callable[..., Any],
    ) -> CORSMiddleware:
        """Return a middleware wrapping the provided ASGI app."""
        return CORSMiddleware(app=app, config=self._config)


__all__ = ["CORSMiddleware", "CORSMiddlewareFactory"]
