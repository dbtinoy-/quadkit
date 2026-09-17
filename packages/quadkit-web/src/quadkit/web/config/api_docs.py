"""API documentation and static file configuration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar
from urllib.parse import urlparse

from quadkit.config import BaseConfig
from quadkit.validation import ConfigDict, Field


@dataclass(init=False)
class APIDocsConfig(BaseConfig):
    """API documentation configuration.

    Documentation assets (Swagger UI, ReDoc) are vendored inside the
    ``quadkit-web`` package and served by the application itself under
    ``/docs-static/`` (plans/09172026 H-03): the default docs pages make no
    third-party requests and the default CSP needs no CDN origins.

    Set ``cdn_base`` to load the same vendored filenames from a CDN or
    private mirror instead (the origin is then auto-allowed in the CSP).
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    enabled: bool = Field(
        default=True,
        description=(
            "Enable API documentation endpoints (/docs, /redoc) and auto-configure "
            "CSP for their assets"
        ),
    )
    provider: str = Field(
        default="both",
        description="Documentation provider: 'swagger', 'redoc', or 'both'",
    )
    cdn_base: str | None = Field(
        default=None,
        description=(
            "Base URL under which the vendored docs asset filenames are served "
            "(e.g. 'https://unpkg.com/swagger-ui-dist@5.10.3' or a private "
            "mirror). Default null: assets are served by the application itself "
            "from /docs-static/ with zero third-party requests. Its origin is "
            "automatically allowed in the CSP when set. Per-asset "
            "web.swagger_js_url / web.swagger_css_url / web.redoc_js_url "
            "overrides take precedence over this base."
        ),
    )

    def get_required_domains(self) -> dict[str, set[str]]:
        """Get required CSP domains for the docs assets.

        Returns an empty mapping in the default (vendored, local) mode: local
        assets are covered by ``'self'`` and require no CSP additions. When
        ``cdn_base`` is set, its origin is allowed for scripts and styles.
        """
        if not self.cdn_base:
            return {}

        parsed = urlparse(
            self.cdn_base if "//" in self.cdn_base else f"https://{self.cdn_base}"
        )
        if not parsed.netloc:
            return {}

        origin = f"{parsed.scheme}://{parsed.netloc}"
        return {
            "script-src": {origin},
            "script-src-elem": {origin},
            "style-src": {origin},
            "style-src-elem": {origin},
        }

    def assets_mode(
        self,
        swagger_js_url: str | None = None,
        swagger_css_url: str | None = None,
        redoc_js_url: str | None = None,
    ) -> str:
        """Report which asset mode the docs pages will use.

        Returns ``"local"`` (vendored assets served by the app), ``"cdn"``
        (``cdn_base`` set) or ``"custom"`` (explicit per-asset URLs) — used
        for the boot log so operators can see the active mode.
        """
        if swagger_js_url or swagger_css_url or redoc_js_url:
            return "custom"
        if self.cdn_base:
            return "cdn"
        return "local"


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
