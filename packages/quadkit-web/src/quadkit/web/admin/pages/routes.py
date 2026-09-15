from __future__ import annotations

from typing import Any

from quadkit.contracts.admin import PageContent
from quadkit.contracts.admin.widget_content import (
    EmptyContent,
    TableCell,
    TableContent,
)
from quadkit.logging import get_logger
from quadkit.web.routing.registry import RouteRegistry

logger = get_logger(__name__)


class WebRoutesPage:
    """Route listing page for /admin/web/routes."""

    def __init__(self, route_registry: RouteRegistry | None = None) -> None:
        self._route_registry = route_registry

    async def handle(self, request: Any) -> PageContent:
        if self._route_registry is None:
            return PageContent(
                title="Routes",
                body=EmptyContent(
                    title="Route Registry Unavailable",
                    message="The route registry could not be resolved. No routes to display.",
                    icon="map",
                ),
            )

        try:
            routes = self._route_registry.get_all_routes()
        except Exception as exc:
            logger.warning("web_routes.fetch_failed", error=str(exc))
            return PageContent(
                title="Routes",
                body=EmptyContent(
                    title="Route Registry Unavailable",
                    message=f"Failed to fetch routes: {exc}",
                    icon="alert-triangle",
                ),
            )

        rows = tuple(
            (
                TableCell(method),
                TableCell(path),
                TableCell(info.get("summary") or info.get("handler_name", "")),
                TableCell(
                    f"{info.get('controller').__name__}.{info.get('handler_name', '')}"
                    if info.get("controller")
                    else info.get("handler_name", "")
                ),
            )
            for path, methods in routes.items()
            for method, info in methods.items()
        )

        if not rows:
            return PageContent(
                title="Routes",
                body=EmptyContent(
                    title="No Routes Registered",
                    message="No routes have been registered yet.",
                    icon="map",
                ),
            )

        return PageContent(
            title="Routes",
            body=TableContent(
                columns=("Method", "Path", "Name", "Handler"),
                rows=rows,
            ),
        )
