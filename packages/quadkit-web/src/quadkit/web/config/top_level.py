"""Top-level web configuration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, cast

from quadkit.config import BaseConfig
from quadkit.contracts.core.config import Environment
from quadkit.validation import (
    ConfigDict,
    Field,
    SecretStr,
    model_validator,
)
from quadkit.web import constants as const
from quadkit.web.config.api_docs import APIDocsConfig, StaticFileConfig
from quadkit.web.config.rate_limit import RateLimitConfig, RoleGuardConfig
from quadkit.web.config.server import ServerConfig
from quadkit.web.security.config import (
    CORSConfig,
    CSRFConfig,
    SecurityConfig,
)


@dataclass(init=False)
class WebConfig(BaseConfig):
    """Hierarchical root configuration for Quadkit Web.

    This is the single source of truth for web configuration,
    loaded from application.yaml's `web` section.

    Attributes:
        name: Configuration name (default: "web")
        enabled: Whether the web module is enabled
        server: Server binding and worker settings
        app: Application-level settings (OpenAPI, CORS origins, etc.)
        security: Security headers and policies
        cors: CORS configuration
        rate_limit: Rate limiting rules
        debug_routes: Enable /debug/* endpoints
        enable_identity_resolution: Resolve OAuth external IDs to internal UUIDs
        enable_auth: Enable built-in authentication middleware
        auth_exclude_paths: Paths excluded from authentication
    """

    config_section: ClassVar[str] = "web"

    model_config = cast(
        "ConfigDict",
        {
            "env_prefix": "QK_WEB__",
            "env_nested_delimiter": "__",
            "extra": "ignore",
        },
    )

    name: str = "web"
    enabled: bool = True
    env: Environment | None = Field(default=None, description="Deployment environment")
    server: ServerConfig = Field(default_factory=ServerConfig)
    security: SecurityConfig = Field(
        default_factory=lambda: SecurityConfig(
            csrf=CSRFConfig(
                enabled=True,
                excluded_paths=["/health", "/metrics", "/admin"],
            ),
        ),
        description="Security configuration (HSTS, CSP, cross-origin, CSRF, headers)",
    )
    cors: CORSConfig = Field(
        default_factory=lambda: CORSConfig(
            allowed_origins=["http://localhost:3000", "http://localhost:8001"],
            allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        ),
    )
    static: StaticFileConfig = Field(default_factory=StaticFileConfig)
    rate_limit: RateLimitConfig = Field(default_factory=RateLimitConfig)

    # OpenAPI settings (formerly in WebAppConfig)
    openapi_title: str = Field(default="API", description="OpenAPI Title")
    openapi_version: str = Field(default="1.0.0", description="OpenAPI Version")
    openapi_url: str | None = Field(default=const.DEFAULT_OPENAPI_PATH)
    swagger_ui_url: str | None = Field(default=const.DEFAULT_DOCS_PATH)
    redoc_url: str | None = Field(default="/redoc")
    swagger_js_url: str | None = Field(default=None)
    swagger_css_url: str | None = Field(default=None)
    redoc_js_url: str | None = Field(default=None)
    compression_enabled: bool = Field(default=True)
    template_directory: str = Field(
        default="templates", description="Directory for Jinja2 templates"
    )

    # API Documentation - auto-configures CSP for /docs and /redoc
    api_docs: APIDocsConfig = Field(
        default_factory=APIDocsConfig,
        description="API documentation configuration (auto-configures CSP)",
    )

    # Debug routes - enable /debug/* endpoints
    debug_routes: bool = Field(default=False, description="Enable debug routes")
    enable_debug_routes_env_gate: bool = Field(
        default=False,
        description="Require explicit opt-in for debug route registration.",
    )
    debug_routes_token: SecretStr | None = Field(
        default=None,
        description="Token required to access debug routes (sent as X-Debug-Token header).",
    )

    # OAuth Identity Resolution - resolve external OAuth IDs to internal UUIDs
    enable_identity_resolution: bool = Field(
        default=False,
        description="Automatically resolve OAuth external IDs to internal UUIDs in authenticated requests",
    )

    # Authentication - enable built-in authentication middleware
    enable_auth: bool = Field(
        default=False,
        description="Enable built-in authentication middleware. Requires authenticators to be registered in the container.",
    )

    # Request body size limit — protects against OOM DoS via oversized payloads.
    # Set to None to disable the middleware entirely.
    max_body_size: int | None = Field(
        default=10 * 1024 * 1024,  # 10 MiB
        ge=1,
        description=(
            "Maximum allowed request body size in bytes. "
            "Requests with a Content-Length header exceeding this limit receive "
            "a 413 response before the body is read. "
            "Set to None to disable the body size limit (not recommended in production)."
        ),
    )

    # Paths to exclude from authentication (e.g., health checks, docs)
    auth_exclude_paths: list[str] = Field(
        default_factory=lambda: [
            const.DEFAULT_HEALTH_PATH,
            const.DEFAULT_HEALTH_PATH + "/",
            const.DEFAULT_DOCS_PATH,
            "/redoc",
            const.DEFAULT_OPENAPI_PATH,
        ],
        description="Paths to exclude from authentication",
    )

    # Role guard — declarative path-to-role enforcement (requires a bound
    # RoleResolverProtocol in the container when rules are declared).
    role_guard: RoleGuardConfig = Field(
        default_factory=RoleGuardConfig,
        description="Role guard rules (path -> allowed roles)",
    )

    @model_validator(mode="after")
    def validate_production_security(self) -> WebConfig:
        """Block insecure configurations in production."""
        if (
            self.cors.allowed_origins
            and "*" in self.cors.allowed_origins
            and self.cors.allow_credentials
        ):
            raise ValueError(
                "CRITICAL SECURITY ERROR: wildcard CORS origin '*' combined with "
                "allow_credentials=True is not permitted in any environment — "
                "set specific origins via QK_WEB__CORS__ALLOWED_ORIGINS.",
            )
        if self.environment == Environment.PRODUCTION:
            if self.cors.allowed_origins and "*" in self.cors.allowed_origins:
                raise ValueError(
                    "CRITICAL SECURITY ERROR: Wildcard CORS origin '*' not allowed in PRODUCTION.\n"
                    "You MUST set specific origins via QK_WEB__CORS__ALLOWED_ORIGINS.",
                )
            if not self.security.csrf.enabled:
                raise ValueError(
                    "CRITICAL SECURITY ERROR: CSRF protection is disabled in PRODUCTION.\n"
                    "You MUST enable it via QK_WEB__SECURITY__CSRF__ENABLED.",
                )
            csrf_key: str | None = (
                self.security.csrf.secret_key.get_secret_value()
                if isinstance(self.security.csrf.secret_key, SecretStr)
                else self.security.csrf.secret_key
            )
            if not csrf_key or csrf_key.strip() == "":
                raise ValueError(
                    "CRITICAL SECURITY ERROR: CSRF is enabled but no secret_key is set in PRODUCTION.\n"
                    "You MUST set one via QK_WEB__SECURITY__CSRF__SECRET_KEY.",
                )
            if not self.security.allowed_hosts:
                raise ValueError(
                    "CRITICAL SECURITY ERROR: no allowed_hosts configured for PRODUCTION.\n"
                    "You MUST configure QK_WEB__SECURITY__ALLOWED_HOSTS "
                    "(host validation fails closed).",
                )
            # HSTS must be on in production (mirrors create_production_config).
            self.security.hsts.enabled = True
        return self


__all__ = [
    "WebConfig",
]
