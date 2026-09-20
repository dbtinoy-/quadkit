"""OpenAPI template helpers for Swagger and Redoc UI.

Provides small wrappers used by `web.routing.openapi.register_openapi_routes` to
render the `templates/swagger.html` and `templates/redoc.html` templates via
`Jinja2Templates`.

Docs assets (plans/09172026 H-03) resolve per-asset with this precedence:
explicit ``web.swagger_js_url``-style overrides, then ``web.api_docs.cdn_base``
+ vendored filename, then the application-served vendored files under
``/docs-static/``. The templates' own fallbacks are the local paths, so a
default application renders with zero third-party requests.
"""

from __future__ import annotations

import html as _html
from pathlib import Path
from typing import TYPE_CHECKING, Any

from quadkit.web.templates.core import Jinja2Templates

if TYPE_CHECKING:
    from quadkit.web.config import WebConfig

TEMPLATE_DIR = Path(__file__).parent.parent / "templates"

#: URL prefix under which the vendored docs assets are served by the app.
LOCAL_DOCS_ASSETS_PREFIX = "/docs-static"

_VENDORED_ASSETS = frozenset(
    {
        "swagger-ui.css",
        "swagger-ui-bundle.js",
        "swagger-ui-standalone-preset.js",
        "swagger-init.js",
        "docs.css",
        "oauth2-redirect.html",
        "redoc.standalone.js",
    }
)


def _resolve_asset_url(
    explicit: str | None,
    cdn_base: str | None,
    filename: str,
    root_path: str = "",
) -> str:
    if filename not in _VENDORED_ASSETS:  # pragma: no cover - defensive
        msg = f"unknown vendored docs asset: {filename}"
        raise ValueError(msg)
    if explicit:
        return explicit
    if cdn_base:
        return f"{cdn_base.rstrip('/')}/{filename}"
    return f"{root_path}{LOCAL_DOCS_ASSETS_PREFIX}/{filename}"


def docs_asset_urls(
    web_config: WebConfig,
    root_path: str = "",
) -> dict[str, str]:
    """Resolve every docs UI asset URL for the configured mode.

    Args:
        web_config: The web configuration (per-asset overrides and
            ``api_docs.cdn_base``).
        root_path: ASGI root_path prefix (apps mounted under a sub-path) —
            only used for locally served assets.

    Returns:
        Mapping of template context keys to asset URLs.
    """
    api_docs = getattr(web_config, "api_docs", None)
    cdn_base = getattr(api_docs, "cdn_base", None) if api_docs is not None else None

    def resolve(explicit: str | None, filename: str) -> str:
        return _resolve_asset_url(explicit, cdn_base, filename, root_path)

    return {
        "swagger_js_url": resolve(web_config.swagger_js_url, "swagger-ui-bundle.js"),
        "swagger_preset_url": resolve(None, "swagger-ui-standalone-preset.js"),
        "swagger_css_url": resolve(web_config.swagger_css_url, "swagger-ui.css"),
        "swagger_init_url": resolve(None, "swagger-init.js"),
        "docs_css_url": resolve(None, "docs.css"),
        "redoc_js_url": resolve(web_config.redoc_js_url, "redoc.standalone.js"),
    }


def swagger_asset_urls(
    web_config: WebConfig,
    root_path: str = "",
) -> dict[str, str]:
    """Asset URLs for the Swagger UI page (keys match get_swagger_ui_html)."""
    urls = docs_asset_urls(web_config, root_path)
    return {
        key: urls[key]
        for key in (
            "swagger_js_url",
            "swagger_preset_url",
            "swagger_css_url",
            "swagger_init_url",
            "docs_css_url",
        )
    }


def redoc_asset_urls(
    web_config: WebConfig,
    root_path: str = "",
) -> dict[str, str]:
    """Asset URLs for the ReDoc page (keys match get_redoc_html)."""
    urls = docs_asset_urls(web_config, root_path)
    return {
        key: urls[key]
        for key in (
            "redoc_js_url",
            "docs_css_url",
        )
    }


def _fallback_html(title: str, openapi_url: str, tool_name: str) -> str:
    """Render a minimal OpenAPI fallback page."""
    safe_title = _html.escape(title)
    safe_url = _html.escape(openapi_url)
    safe_tool = _html.escape(tool_name)
    return (
        f"<!DOCTYPE html><html><head><title>{safe_title}</title></head>"
        f"<body><h1>{safe_title}</h1>"
        f'<p>OpenAPI JSON: <a href="{safe_url}">{safe_url}</a></p>'
        f"<p>Install jinja2 to enable the full {safe_tool} UI.</p>"
        "</body></html>"
    )


def get_swagger_ui_html(
    title: str,
    openapi_url: str,
    swagger_js_url: str | None = None,
    swagger_css_url: str | None = None,
    swagger_preset_url: str | None = None,
    swagger_init_url: str | None = None,
    docs_css_url: str | None = None,
) -> str:
    """Render the Swagger UI HTML from template."""
    try:
        templates = Jinja2Templates(directory=TEMPLATE_DIR)
        context: dict[str, Any] = {
            "title": title,
            "openapi_url": openapi_url,
            "swagger_js_url": swagger_js_url,
            "swagger_css_url": swagger_css_url,
            "swagger_preset_url": swagger_preset_url,
            "swagger_init_url": swagger_init_url,
            "docs_css_url": docs_css_url,
        }
        return templates.render_template("swagger.html", context)
    except Exception:  # noqa: BLE001 — the docs UI is best-effort; any rendering failure falls back to plain HTML
        return _fallback_html(title, openapi_url, "Swagger")


def get_redoc_html(
    title: str,
    openapi_url: str,
    redoc_js_url: str | None = None,
    docs_css_url: str | None = None,
) -> str:
    """Render the ReDoc HTML from template."""
    try:
        templates = Jinja2Templates(directory=TEMPLATE_DIR)
        context: dict[str, Any] = {
            "title": title,
            "openapi_url": openapi_url,
            "redoc_js_url": redoc_js_url,
            "docs_css_url": docs_css_url,
        }
        return templates.render_template("redoc.html", context)
    except Exception:  # noqa: BLE001 — the docs UI is best-effort; any rendering failure falls back to plain HTML
        return _fallback_html(title, openapi_url, "ReDoc")
