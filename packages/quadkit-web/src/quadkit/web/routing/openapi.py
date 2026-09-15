"""OpenAPI route registration for quadkit-web."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from starlette.responses import HTMLResponse, JSONResponse

if TYPE_CHECKING:
    from quadkit.web.di.provider import WebProvider


def register_openapi_routes(provider: WebProvider) -> None:
    """Register OpenAPI documentation routes."""
    starlette = provider.starlette
    if starlette is None:
        raise RuntimeError("Starlette application not initialized")
    cfg = provider.web_config

    async def openapi_json(_request: Any) -> JSONResponse:
        spec = provider.router_manager.generate_openapi_spec()
        return JSONResponse(spec)

    async def swagger_ui(_request: Any) -> HTMLResponse:
        from quadkit.web.routing.openapi_templates import (
            get_swagger_ui_html,
        )

        return HTMLResponse(
            get_swagger_ui_html(
                title=cfg.openapi_title,
                openapi_url=cast("str", cfg.openapi_url),
                swagger_js_url=cfg.swagger_js_url,
                swagger_css_url=cfg.swagger_css_url,
            ),
        )

    async def redoc_ui(_request: Any) -> HTMLResponse:
        from quadkit.web.routing.openapi_templates import (
            get_redoc_html,
        )

        return HTMLResponse(
            get_redoc_html(
                title=cfg.openapi_title,
                openapi_url=cast("str", cfg.openapi_url),
                redoc_js_url=cfg.redoc_js_url,
            ),
        )

    if cfg.openapi_url:
        starlette.add_route(
            cfg.openapi_url,
            openapi_json,
            methods=["GET"],
            name="openapi",
        )
    if cfg.swagger_ui_url:
        starlette.add_route(
            cfg.swagger_ui_url,
            swagger_ui,
            methods=["GET"],
            name="swagger_ui",
        )
    if cfg.redoc_url:
        starlette.add_route(
            cfg.redoc_url,
            redoc_ui,
            methods=["GET"],
            name="redoc_ui",
        )
