"""API documentation and static file configuration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from quadkit.config import BaseConfig
from quadkit.validation import ConfigDict, Field


@dataclass(init=False)
class APIDocsConfig(BaseConfig):
    """API documentation configuration.

    Automatically configures CSP directives for API documentation endpoints
    (/docs for Swagger UI, /redoc for ReDoc) when enabled.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    enabled: bool = Field(
        default=True,
        description=(
            "Enable API documentation endpoints (/docs, /redoc) and auto-configure "
            "CSP for their CDN assets"
        ),
    )
    provider: str = Field(
        default="both",
        description="Documentation provider: 'swagger', 'redoc', or 'both'",
    )

    # Domains needed for API docs
    SWAGGER_DOMAINS: ClassVar[dict[str, set[str]]] = {
        "script-src": {"https://unpkg.com"},
        "script-src-elem": {"https://unpkg.com"},  # For <script src> elements
        "style-src": {"https://unpkg.com"},
        "style-src-elem": {"https://unpkg.com"},  # For <link rel=stylesheet> elements
    }

    REDOC_DOMAINS: ClassVar[dict[str, set[str]]] = {
        "script-src": {"https://cdn.redoc.ly"},
        "script-src-elem": {"https://cdn.redoc.ly"},  # For <script src> elements
        "style-src": {"https://fonts.googleapis.com"},
        "style-src-elem": {
            "https://fonts.googleapis.com"
        },  # For <link rel=stylesheet> elements
        "font-src": {"https://fonts.gstatic.com"},
        "worker-src": {"blob:"},
    }

    def get_required_domains(self) -> dict[str, set[str]]:
        """Get required CSP domains based on provider setting."""
        result: dict[str, set[str]] = {}

        # Determine which providers to include
        providers = {"swagger", "redoc"} if self.provider == "both" else {self.provider}

        if "swagger" in providers:
            for key, values in self.SWAGGER_DOMAINS.items():
                result.setdefault(key, set()).update(values)

        if "redoc" in providers:
            for key, values in self.REDOC_DOMAINS.items():
                result.setdefault(key, set()).update(values)

        return result


@dataclass(init=False)
class StaticFileConfig(BaseConfig):
    """Static file serving configuration."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    enabled: bool = Field(default=False, description="Enable static file serving")
    directory: str = Field(default="static", description="Directory to serve")
    prefix: str = Field(default="/static", description="URL prefix for static files")
    html: bool = Field(default=False, description="Serve HTML files (SPA mode)")


__all__ = [
    "APIDocsConfig",
    "StaticFileConfig",
]
