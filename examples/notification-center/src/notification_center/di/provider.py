"""Convention followed: **Provider pattern** — ``register()`` declares
singletons, ``boot()`` resolves contracts, ``health_check()`` reports
readiness.

Lifecycle wiring for the Notification Center showcase.

``MailerModule.configure()`` and ``InboxProvider`` (added directly — the
package has no combined "notification core" module bundling mailer and
inbox together) both finish wiring their own object graphs into the
container. This provider only resolves what they exported
(``MailerProtocol``, ``InboxService``) and builds the browser-facing
``NotificationCenterService`` on top, the same "resolve what the package
exported, build the rest in a demo Provider" pattern audit-trail,
secrets-vault, and graph-explorer use.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from notification_center.config import NotificationCenterConfig
from notification_center.controllers.api import NotificationCenterApiController
from quadkit.contracts.core import HealthCheckResult, HealthStatus
from quadkit.contracts.mailer import MailerProtocol
from quadkit.di.provider import Provider
from quadkit.notification.inbox.service import InboxService

if TYPE_CHECKING:
    from quadkit.contracts.core.di import (
        ContainerRegistrarProtocol,
        ContainerResolverProtocol,
    )


class NotificationCenterProvider(Provider):
    """Resolve the package-owned mailer/inbox stack and wire the browser service.

    ``MailerModule.configure()`` exports ``MailerProtocol`` and
    ``InboxProvider`` registers ``InboxService`` directly — this provider
    resolves both, plus the ``NotificationCenterConfig`` singleton, and
    constructs ``NotificationCenterService`` so the console can send real
    email and browse a real per-user inbox.
    """

    name = "notification_center"
    config_key: str | None = "notification_center"
    config_model: type | None = NotificationCenterConfig

    def __init__(self) -> None:
        super().__init__()
        self._service: object | None = None

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        """Bind the demo config singleton.

        Args:
            container: DI registrar received from the framework.
        """
        config = (
            self.config
            if isinstance(self.config, NotificationCenterConfig)
            else NotificationCenterConfig()
        )
        container.singleton(NotificationCenterConfig, config)

    async def boot(self, container: ContainerResolverProtocol) -> None:
        """Resolve the mailer/inbox stack, build the service, seed sample data.

        Args:
            container: DI resolver used to obtain package-owned bindings.
        """
        from notification_center.services.center import NotificationCenterService

        config = await container.resolve(NotificationCenterConfig)
        mailer = await container.resolve(MailerProtocol)
        inbox = await container.resolve(InboxService)

        service = NotificationCenterService(mailer=mailer, inbox=inbox, config=config)
        await service.seed()
        self._service = service

        container.bind(
            NotificationCenterApiController,
            NotificationCenterApiController(service=service),
        )

    async def shutdown(self) -> None:
        """Release the service reference on shutdown."""
        self._service = None

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Delegate health check to the browser-facing service.

        Args:
            timeout: Ignored — the underlying mailer health probe is fast.

        Returns:
            :class:`~quadkit.contracts.core.HealthCheckResult`.
        """
        if self._service is None:
            return HealthCheckResult(
                component="notification_center",
                status=HealthStatus.DEGRADED,
                message="service not booted",
            )
        result = await self._service.health()
        return HealthCheckResult(
            component="notification_center",
            status=HealthStatus(result["status"]),
            details=result["details"],
        )


__all__ = ["NotificationCenterProvider"]
