"""Admin contributor for quadkit-notification — surfaces the persisted
user inbox (InboxService) into the Quadkit admin: bell JSON endpoints,
an inbox management page, and health.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from quadkit.contracts.admin.contributor import BaseAdminContributor
from quadkit.contracts.admin.health_payload import HealthCheckPayload
from quadkit.contracts.admin.types import (
    AdminHealthDefinition,
    AdminRouteSpec,
    ManagementPageDefinition,
    NavigationContribution,
    PageCategory,
)
from quadkit.contracts.core.health import HealthStatus
from quadkit.notification.admin.handlers.inbox import InboxHandlers
from quadkit.notification.inbox.service import InboxService
from quadkit.result import Err, Ok

if TYPE_CHECKING:
    from quadkit.contracts.admin.errors import AdminError
    from quadkit.contracts.core.di import ContainerResolverProtocol
    from quadkit.result import Result

_NAV_ITEMS: tuple[NavigationContribution, ...] = (
    NavigationContribution(
        label="Notifications",
        url="/admin/notifications",
        icon="bell",
        group="infrastructure",
        order=50,
    ),
)

_HEALTH_DEFS: tuple[AdminHealthDefinition, ...] = (
    AdminHealthDefinition(
        name="notifications.inbox",
        contributor="notifications",
        component="Inbox",
        check_endpoint="/admin/notifications/health/inbox",
        description="Verifies the inbox store is reachable.",
    ),
)


class NotificationAdminContributor(BaseAdminContributor):
    """Admin contributor for the quadkit-notification package.

    Surfaces the persisted user inbox: a JSON endpoint backend for the
    topbar notification bell (list + unread count), mark-read /
    mark-all-read round trips, and the /admin/notifications inbox page.
    """

    name = "notifications"
    display_name = "Notifications"
    group = "infrastructure"
    icon = "bell"
    priority = 50

    def __init__(self) -> None:
        self._handlers = InboxHandlers()

    async def on_admin_boot(self, container: ContainerResolverProtocol) -> None:
        """Resolve the inbox service from the container.

        Falls back to an in-memory store when the service is not
        registered (the bell and page keep working in-process).

        Args:
            container: The DI container resolver.
        """
        service = await container.resolve_optional(InboxService)
        self._handlers = InboxHandlers(service=service)

    def get_routes(self) -> Sequence[AdminRouteSpec]:
        """Return inbox JSON endpoints for the notification bell.

        Returns:
            Sequence of AdminRouteSpec for inbox endpoints.
        """
        return [
            AdminRouteSpec(
                path="/admin/notifications/inbox",
                method="GET",
                handler=self._handlers.get_inbox,
                name="inbox.list",
            ),
            AdminRouteSpec(
                path="/admin/notifications/read/{message_id}",
                method="POST",
                handler=self._handlers.mark_read,
                name="inbox.mark_read",
            ),
            AdminRouteSpec(
                path="/admin/notifications/read-all",
                method="POST",
                handler=self._handlers.mark_all_read,
                name="inbox.mark_all_read",
            ),
        ]

    def get_navigation_items(self) -> Sequence[NavigationContribution]:
        """Return navigation items.

        Returns:
            Sequence of NavigationContribution for notifications nav.
        """
        return list(_NAV_ITEMS)

    def get_health_definitions(self) -> Sequence[AdminHealthDefinition]:
        """Return health check definitions.

        Returns:
            Sequence of AdminHealthDefinition for inbox health checks.
        """
        return list(_HEALTH_DEFS)

    def get_management_pages(self) -> Sequence[ManagementPageDefinition]:
        """Return management page definitions.

        Returns:
            Sequence of ManagementPageDefinition for the inbox page.
        """
        return [
            ManagementPageDefinition(
                name="notifications_inbox",
                title="Notifications Inbox",
                contributor="notifications",
                route_path="/notifications",
                handler="quadkit.notification.admin.pages.inbox:NotificationsInboxPage",
                category=PageCategory.INFRASTRUCTURE,
                icon="bell",
                description="Persisted in-app notifications for the current user",
                order=50,
            ),
        ]

    async def render_health_check(
        self,
        check_name: str,
    ) -> Result[HealthCheckPayload, AdminError]:
        """Render the inbox health check fragment.

        Args:
            check_name: Name of the health check to render.

        Returns:
            Ok(payload) for the inbox health check.
        """
        from typing import cast as type_cast

        from quadkit.contracts.admin.errors import AdminError

        if check_name != "notifications.inbox":
            return type_cast(
                "Result[HealthCheckPayload, AdminError]",
                Err(AdminError(f"Unknown health check: {check_name}")),
            )

        try:
            message = await self._handlers.health()
        except Exception as exc:  # noqa: BLE001 — non-fatal health probe
            return Ok(
                HealthCheckPayload(
                    status=HealthStatus.DEGRADED,
                    component="Inbox",
                    detail=str(exc),
                )
            )
        return Ok(
            HealthCheckPayload(
                status=HealthStatus.HEALTHY,
                component="Inbox",
                detail=message,
            )
        )


__all__ = ["NotificationAdminContributor"]
