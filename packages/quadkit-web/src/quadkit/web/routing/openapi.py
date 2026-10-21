"""OpenAPI route registration for quadkit-web."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from quadkit.logging import get_logger
from quadkit.web.transport.responses import HTMLResponse, JSONResponse

if TYPE_CHECKING:
    from quadkit.web.di.provider import WebProvider

logger = get_logger(__name__)


def register_openapi_routes(provider: WebProvider) -> None:
    """Register OpenAPI documentation routes when the app serves them.

    ``/openapi.json``, ``/docs`` and ``/redoc`` follow
    :attr:`~quadkit.web.config.WebConfig.api_docs_enabled`: withheld in
    production unless ``web.api_docs.enabled`` opts in explicitly, and
    withheld everywhere when it is ``false``.
    """
    starlette = provider.starlette
    if starlette is None:
        raise RuntimeError("Starlette application not initialized")
    cfg = provider.web_config

    if not cfg.api_docs_enabled:
        logger.info(
            "api_docs_withheld",
            environment=cfg.environment.value,
            hint=(
                "set web.api_docs.enabled=true to serve /docs, /redoc and /openapi.json"
            ),
        )
        return

    async def openapi_json(_request: Any) -> JSONResponse:
        spec = provider.router_manager.generate_openapi_spec()
        return JSONResponse(spec)

    async def swagger_ui(request: Any) -> HTMLResponse:
        from quadkit.web.routing.openapi_templates import (
            get_swagger_ui_html,
            swagger_asset_urls,
        )

        return HTMLResponse(
            get_swagger_ui_html(
                title=cfg.openapi_title,
                openapi_url=cast("str", cfg.openapi_url),
                **swagger_asset_urls(cfg, request.scope.get("root_path", "")),
            ),
        )

    async def redoc_ui(request: Any) -> HTMLResponse:
        from quadkit.web.routing.openapi_templates import (
            get_redoc_html,
            redoc_asset_urls,
        )

        return HTMLResponse(
            get_redoc_html(
                title=cfg.openapi_title,
                openapi_url=cast("str", cfg.openapi_url),
                **redoc_asset_urls(cfg, request.scope.get("root_path", "")),
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
