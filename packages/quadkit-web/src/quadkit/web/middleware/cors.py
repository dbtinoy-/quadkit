"""CORS middleware wrapper for quadkit-web security primitives."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from quadkit.logging import get_logger
from quadkit.web.security.config import CORSConfig
from quadkit.web.security.cors.middleware import CORSMiddleware as WebCORSMiddleware

logger = get_logger(__name__)


class CORSMiddleware(WebCORSMiddleware):
    """CORS middleware with web-compatible interface.

    Wraps :class:`quadkit.web.security.cors.middleware.CORSMiddleware`
    while still accepting Starlette-style keyword arguments.
    """

    def __init__(
        self,
        app: Any,
        config: Any = None,
        **kwargs: Any,
    ) -> None:
        """Initialize CORS middleware with optional config conversion.

        Args:
            app: ASGI application.
            config: CORSConfig instance or duck-typed equivalent.
            **kwargs: Additional kwargs as fallback for config values.
        """
        super().__init__(app=app, config=self._convert_config(config, kwargs))

    @staticmethod
    def _convert_config(config: Any, kwargs: dict[str, Any]) -> CORSConfig:
        """Convert various config formats to CORSConfig.

        Args:
            config: Configuration object (CORSConfig or duck-typed equivalent).
            kwargs: Keyword arguments as fallback.

        Returns:
            CORSConfig instance.
        """
        if config is None:
            return CORSConfig(
                allowed_origins=kwargs.get("allow_origins", []),
                allow_credentials=kwargs.get("allow_credentials", False),
                allow_methods=kwargs.get(
                    "allow_methods",
                    ["GET", "POST", "PUT", "DELETE", "PATCH"],
                ),
                allow_headers=kwargs.get("allow_headers", ["*"]),
                expose_headers=kwargs.get("expose_headers", []),
                max_age=kwargs.get("max_age", 600),
            )

        if isinstance(config, CORSConfig):
            return config

        if hasattr(config, "to_middleware_kwargs"):
            cors_kwargs = config.to_middleware_kwargs()
            return CORSConfig(
                allowed_origins=cors_kwargs.get("allow_origins", []),
                allow_credentials=cors_kwargs.get("allow_credentials", False),
                allow_methods=cors_kwargs.get(
                    "allow_methods", ["GET", "POST", "PUT", "DELETE", "PATCH"]
                ),
                allow_headers=cors_kwargs.get("allow_headers", ["*"]),
                expose_headers=cors_kwargs.get("expose_headers", []),
                max_age=cors_kwargs.get("max_age", 600),
            )

        return CORSConfig(
            allowed_origins=getattr(config, "allow_origins", []),
            allow_credentials=getattr(config, "allow_credentials", False),
            allow_methods=getattr(
                config,
                "allow_methods",
                ["GET", "POST", "PUT", "DELETE", "PATCH"],
            ),
            allow_headers=getattr(config, "allow_headers", ["*"]),
            expose_headers=getattr(config, "expose_headers", []),
            max_age=getattr(config, "max_age", 600),
        )


def create_development_cors() -> CORSConfig:
    """Create CORS config for development (permissive).

    WARNING: Never use in production!

    Returns:
        Development CORS config
    """
    logger.warning(
        "Using development CORS configuration. "
        "This allows all origins - DO NOT USE IN PRODUCTION!",
    )

    return CORSConfig(
        allow_origins=["*"],
        allow_credentials=False,  # Can't use credentials with wildcard
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    )


def create_production_cors(
    allowed_domains: Sequence[str],
    allow_credentials: bool = True,
) -> CORSConfig:
    """Create CORS config for production (strict).

    Args:
        allowed_domains: Exact domains to allow (e.g., ["https://myapp.com"])
        allow_credentials: Whether to allow credentials

    Returns:
        Production CORS config
    """
    return CORSConfig(
        allow_origins=list(allowed_domains),
        allow_credentials=allow_credentials,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        expose_headers=["Content-Length", "Content-Type"],
    )


__all__ = ["CORSMiddleware", "create_development_cors", "create_production_cors"]
