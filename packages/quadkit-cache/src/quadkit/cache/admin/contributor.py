"""Admin contributor for quadkit-cache — surfaces cache hit/miss, eviction,
and backend-ping widgets into the Quadkit admin dashboard.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, cast

from quadkit.contracts.admin.contributor import BaseAdminContributor
from quadkit.contracts.admin.errors import WidgetNotFoundError
from quadkit.contracts.admin.types import (
    AdminActionDefinition,
    AdminHealthDefinition,
    AdminRouteSpec,
    DashboardWidgetDefinition,
    ManagementPageDefinition,
    NavigationContribution,
    PageCategory,
    WidgetCategory,
    WidgetKind,
    WidgetParams,
    WidgetSize,
    WidgetViewModel,
)
from quadkit.result import Err, Ok, Result

if TYPE_CHECKING:
    from quadkit.contracts.admin.errors import AdminError
    from quadkit.contracts.core.di import ContainerResolverProtocol

from quadkit.contracts.admin.widget_protocols import WidgetHandlerProtocol
from quadkit.logging import get_logger


async def _empty_handler(request: object) -> str:  # noqa: ARG001
    """Placeholder handler for contributed routes.

    Routes registered via ``get_routes()`` prove the registration surface works.
    Full widget rendering uses the existing ``WidgetController`` path.
    """
    return ""


logger = get_logger(__name__)

_WIDGETS: tuple[DashboardWidgetDefinition, ...] = (
    DashboardWidgetDefinition(
        name="hit_miss_ratio",
        title="Hit / Miss Ratio",
        contributor="cache",
        render_endpoint="/admin/cache/widgets/hit_miss_ratio",
        size=WidgetSize.LARGE,
        category=WidgetCategory.METRICS,
        view_kind=WidgetKind.STAT,
        description="Cache hit and miss ratio over the last rolling window.",
    ),
    DashboardWidgetDefinition(
        name="eviction_rate",
        title="Eviction Rate",
        contributor="cache",
        render_endpoint="/admin/cache/widgets/eviction_rate",
        size=WidgetSize.SMALL,
        category=WidgetCategory.METRICS,
        view_kind=WidgetKind.STAT,
        description="Number of keys evicted per second.",
    ),
    DashboardWidgetDefinition(
        name="backend_ping",
        title="Backend Ping",
        contributor="cache",
        render_endpoint="/admin/cache/widgets/backend_ping",
        size=WidgetSize.SMALL,
        category=WidgetCategory.HEALTH,
        view_kind=WidgetKind.HEALTH,
        description="Round-trip latency to the cache backend.",
    ),
)

_NAV_ITEMS: tuple[NavigationContribution, ...] = (
    NavigationContribution(
        label="Cache",
        url="/admin/cache",
        icon="zap",
        group="infrastructure",
        order=20,
        children=(
            NavigationContribution(
                label="Keys",
                url="/admin/cache/keys",
                icon="key",
                group="infrastructure",
                order=10,
            ),
            NavigationContribution(
                label="Stats",
                url="/admin/cache/stats",
                icon="bar-chart",
                group="infrastructure",
                order=20,
            ),
        ),
    ),
)

_HEALTH_DEFS: tuple[AdminHealthDefinition, ...] = (
    AdminHealthDefinition(
        name="cache.backend",
        contributor="cache",
        component="Cache Backend",
        check_endpoint="/admin/cache/health/backend",
        description="Verifies the configured cache backend is reachable.",
    ),
)

_ACTIONS: tuple[AdminActionDefinition, ...] = (
    AdminActionDefinition(
        name="flush_cache",
        title="Flush Cache",
        contributor="cache",
        handler="quadkit.cache.admin.actions:flush_cache",
        icon="trash-2",
        confirmation_message="This will delete all cached keys. Are you sure?",
        destructive=True,
        category="operations",
    ),
    AdminActionDefinition(
        name="warm_cache",
        title="Warm Cache",
        contributor="cache",
        handler="quadkit.cache.admin.actions:warm_cache",
        icon="flame",
        category="operations",
    ),
)


class CacheAdminContributor(BaseAdminContributor):
    """Admin contributor for the quadkit-cache package.

    Registered via ``the optional provider module`` entry point.
    Provides cache hit/miss ratio, eviction rate, and backend ping widgets.
    Dependencies are resolved from the container in ``on_admin_boot``.
    """

    name = "cache"
    display_name = "Cache"
    group = "infrastructure"
    icon = "zap"
    priority = 20

    def __init__(self) -> None:
        self._handlers: dict[str, WidgetHandlerProtocol] | None = None

    async def on_admin_boot(self, container: ContainerResolverProtocol) -> None:
        """Resolve cache admin dependencies from the DI container.

        Args:
            container: The DI container resolver.
        """
        from quadkit.cache.admin.handlers.backend_ping import (
            BackendPingWidgetHandler,
        )
        from quadkit.cache.admin.handlers.eviction_rate import (
            EvictionRateWidgetHandler,
        )
        from quadkit.cache.admin.handlers.hit_miss_ratio import (
            HitMissRatioWidgetHandler,
        )
        from quadkit.contracts.infra.cache.protocols import CacheBackendProtocol

        try:
            cache = await container.resolve(CacheBackendProtocol)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "cache_contributor.cache_backend_unavailable", error=str(exc)
            )
            cache = None

        if cache is not None:
            self._handlers = {
                "hit_miss_ratio": HitMissRatioWidgetHandler(cache=cache),
                "eviction_rate": EvictionRateWidgetHandler(cache=cache),
                "backend_ping": BackendPingWidgetHandler(cache=cache),
            }
        else:
            self._handlers = None

    def get_routes(self) -> Sequence[AdminRouteSpec]:
        return [
            AdminRouteSpec(
                path=w.render_endpoint,
                method="GET",
                handler=_empty_handler,
                name=f"widgets.{w.name}",
            )
            for w in _WIDGETS
        ]

    def get_dashboard_widgets(self) -> Sequence[DashboardWidgetDefinition]:
        return list(_WIDGETS)

    def get_navigation_items(self) -> Sequence[NavigationContribution]:
        return list(_NAV_ITEMS)

    def get_health_definitions(self) -> Sequence[AdminHealthDefinition]:
        return list(_HEALTH_DEFS)

    def get_actions(self) -> Sequence[AdminActionDefinition]:
        return list(_ACTIONS)

    def get_management_pages(self) -> Sequence[ManagementPageDefinition]:
        return [
            ManagementPageDefinition(
                name="cache_overview",
                title="Cache Overview",
                contributor="cache",
                route_path="/cache",
                handler="quadkit.cache.admin.pages.overview:CacheOverviewPage",
                category=PageCategory.INFRASTRUCTURE,
                icon="zap",
                description="Cache backend metrics and status",
                order=10,
            ),
            ManagementPageDefinition(
                name="cache_keys",
                title="Cache Keys",
                contributor="cache",
                route_path="/cache/keys",
                handler="quadkit.cache.admin.pages.keys:CacheKeysPage",
                category=PageCategory.INFRASTRUCTURE,
                icon="key",
                description="Browse and search cached keys",
                order=20,
            ),
            ManagementPageDefinition(
                name="cache_stats",
                title="Cache Stats",
                contributor="cache",
                route_path="/cache/stats",
                handler="quadkit.cache.admin.pages.stats:CacheStatsPage",
                category=PageCategory.INFRASTRUCTURE,
                icon="bar-chart",
                description="Detailed cache performance statistics",
                order=30,
            ),
        ]

    async def render_widget(
        self,
        widget_name: str,
        params: WidgetParams,
        resolver: ContainerResolverProtocol | None = None,
    ) -> Result[WidgetViewModel, AdminError]:
        """Render a named widget using registry dispatch.

        Args:
            widget_name: Name of the widget to render.
            params: Typed widget parameters.

        Returns:
            Ok(html_str) on success.
            Err(WidgetNotFoundError) if widget_name not served by this contributor.
            Infrastructure exceptions propagate.
        """
        # Registry dispatch
        if self._handlers is None:
            return Err(WidgetNotFoundError(self.name, widget_name))  # type: ignore[arg-type]
        handler = self._handlers.get(widget_name)
        if handler is None:
            return Err(WidgetNotFoundError(self.name, widget_name))  # type: ignore[arg-type]

        # Fetch data via handler
        data_result = await handler.get_data(params)
        if data_result.is_err():
            return Err(data_result.unwrap_err())

        content = data_result.unwrap()
        return cast(
            "Result[WidgetViewModel, AdminError]",
            Ok(WidgetViewModel(content=content)),
        )


__all__ = ["CacheAdminContributor"]
