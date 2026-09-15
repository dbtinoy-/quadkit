from __future__ import annotations

from typing import Any

from quadkit.contracts.admin import PageContent
from quadkit.contracts.admin.widget_content import Stat, StatContent
from quadkit.logging import get_logger
from quadkit.web.routing.controller_registry import ControllerRegistry
from quadkit.web.routing.registry import RouteRegistry

logger = get_logger(__name__)


class WebOverviewPage:
    """Dashboard overview for /admin/web."""

    def __init__(
        self,
        route_registry: RouteRegistry | None = None,
        controller_registry: ControllerRegistry | None = None,
    ) -> None:
        self._route_registry = route_registry
        self._controller_registry = controller_registry

    async def handle(self, request: Any) -> PageContent:
        total_routes = 0
        total_controllers = 0

        try:
            if self._route_registry is not None:
                routes = self._route_registry.get_all_routes()
                total_routes = sum(len(methods) for methods in routes.values())
        except Exception as exc:
            logger.warning("web_overview.routes_unavailable", error=str(exc))

        try:
            if self._controller_registry is not None:
                total_controllers = len(self._controller_registry.get_all_controllers())
        except Exception as exc:
            logger.warning("web_overview.controllers_unavailable", error=str(exc))

        return PageContent(
            title="Web",
            body=StatContent(
                stats=(
                    Stat(
                        label="Total Routes",
                        value=str(total_routes),
                        icon="map",
                    ),
                    Stat(
                        label="Total Controllers",
                        value=str(total_controllers),
                        icon="layers",
                    ),
                )
            ),
        )
