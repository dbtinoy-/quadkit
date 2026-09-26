"""Admin DI provider: registers AuthAdminContributor."""

from __future__ import annotations

from typing import TYPE_CHECKING

from quadkit.contracts.core.provider import ProviderPriority
from quadkit.di.provider import Provider
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.auth.config import AuthConfig
    from quadkit.contracts.core.di import (
        ContainerRegistrarProtocol,
        ContainerResolverProtocol,
    )

__all__ = ["AuthAdminProvider"]

logger = get_logger(__name__)


class AuthAdminProvider(Provider):
    """Registers AuthAdminContributor for admin panel integration.

    Args:
        config: Auth configuration.
    """

    def __init__(self, config: AuthConfig | None = None) -> None:
        super().__init__(name="auth_admin", priority=ProviderPriority.LOW)
        self._config = config

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        """Bind admin contributor singleton."""
        from quadkit.auth.admin.contributor import AuthAdminContributor
        from quadkit.auth.admin.handlers.active_sessions import (
            ActiveSessionsWidgetHandler,
        )
        from quadkit.auth.admin.handlers.failed_logins import (
            FailedLoginsWidgetHandler,
        )
        from quadkit.auth.admin.handlers.token_refresh_rate import (
            TokenRefreshRateWidgetHandler,
        )
        from quadkit.auth.services.activity_tracker import AuthActivityTracker

        container.singleton(AuthActivityTracker, AuthActivityTracker)
        container.transient(
            ActiveSessionsWidgetHandler,
            ActiveSessionsWidgetHandler,
        )
        container.transient(
            FailedLoginsWidgetHandler,
            FailedLoginsWidgetHandler,
        )
        container.transient(
            TokenRefreshRateWidgetHandler,
            TokenRefreshRateWidgetHandler,
        )
        container.singleton(AuthAdminContributor, AuthAdminContributor)

    async def boot(self, container: ContainerResolverProtocol) -> None:
        """Boot the auth admin contributor."""
        from quadkit.auth.admin.contributor import AuthAdminContributor

        try:
            contributor = await container.resolve(AuthAdminContributor)
            await contributor.on_admin_boot(container)
            logger.info("auth_admin_contributor.booted")
        except Exception as e:  # noqa: BLE001
            logger.warning(
                "auth_admin_contributor.boot_failed",
                error=str(e),
            )
