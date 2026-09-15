"""OpenAPI template helpers for Swagger and Redoc UI.

Provides small wrappers used by `web.routing.openapi.register_openapi_routes` to
render the `templates/swagger.html` and `templates/redoc.html` templates via
`Jinja2Templates`.
"""

from __future__ import annotations

import html as _html
from pathlib import Path

from quadkit.web.templates.core import Jinja2Templates

TEMPLATE_DIR = Path(__file__).parent.parent / "templates"


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
) -> str:
    """Render the Swagger UI HTML from template."""
    try:
        templates = Jinja2Templates(directory=TEMPLATE_DIR)
        context = {
            "title": title,
            "openapi_url": openapi_url,
            "swagger_js_url": swagger_js_url,
            "swagger_css_url": swagger_css_url,
        }
        return templates.render_template("swagger.html", context)
    except Exception:  # noqa: BLE001 — the docs UI is best-effort; any rendering failure falls back to plain HTML
        return _fallback_html(title, openapi_url, "Swagger")


def get_redoc_html(
    title: str,
    openapi_url: str,
    redoc_js_url: str | None = None,
) -> str:
    """Render the ReDoc HTML from template."""
    try:
        templates = Jinja2Templates(directory=TEMPLATE_DIR)
        context = {
            "title": title,
            "openapi_url": openapi_url,
            "redoc_js_url": redoc_js_url,
        }
        return templates.render_template("redoc.html", context)
    except Exception:  # noqa: BLE001 — the docs UI is best-effort; any rendering failure falls back to plain HTML
        return _fallback_html(title, openapi_url, "ReDoc")
