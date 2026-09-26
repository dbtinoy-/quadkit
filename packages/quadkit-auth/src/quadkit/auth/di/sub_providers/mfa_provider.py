"""MFA provider — registers MFAManager with config from AuthConfig.

Follows the sub-provider pattern (like TokenProvider, SessionProvider):
receives AuthConfig via constructor, no config_key/config_model.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

from quadkit.auth.config import AuthConfig, MFAConfig
from quadkit.auth.mfa.manager import MFAManager
from quadkit.contracts.core import HealthCheckResult, HealthStatus, ProviderPriority
from quadkit.di.decorators import inject
from quadkit.di.markers import Inject
from quadkit.di.provider import Provider
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.contracts.core.di import (
        ContainerRegistrarProtocol,
        ContainerResolverProtocol,
    )

logger = get_logger(__name__)


@inject
class MFAProvider(Provider):
    """Register the MFA manager with config-driven TOTP/backup settings.

    Sub-provider managed by AuthBundleProvider. Receives AuthConfig via
    constructor (same pattern as TokenProvider, SessionProvider).

    Args:
        config: The resolved auth config (carries ``mfa`` section).
    """

    def __init__(
        self,
        config: Annotated[AuthConfig, Inject] | None = None,
    ) -> None:
        super().__init__(name="mfa", priority=ProviderPriority.SECURITY)
        self._config = config

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        """Register MFAManager with MFAConfig from AuthConfig.

        The factory resolves UserStoreProtocol at resolution time (after
        AuthenticationProvider has registered it).
        """
        mfa_config = self._config.mfa if self._config else MFAConfig()

        async def build_mfa(resolver: Any) -> MFAManager:
            from quadkit.auth.storage.token_store import UserStoreProtocol

            user_store = await resolver.resolve(UserStoreProtocol)
            return MFAManager(user_store=user_store, config=mfa_config)

        container.singleton(MFAManager, factory=build_mfa)

    async def boot(self, container: ContainerResolverProtocol) -> None:
        """Initialize MFA provider."""
        logger.info("mfa_provider.booted")

    async def shutdown(self) -> None:
        """Shutdown MFA provider."""
        logger.info("mfa_provider.shutdown")

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Check MFA provider health."""
        mfa_config = self._config.mfa if self._config else MFAConfig()
        return HealthCheckResult(
            component=self.name,
            status=HealthStatus.HEALTHY,
            details={
                "totp_digits": mfa_config.totp.digits,
                "totp_interval": mfa_config.totp.interval,
                "backup_count": mfa_config.backup.count,
                "max_attempts": mfa_config.max_challenge_attempts,
            },
        )


__all__ = [
    "MFAProvider",
    "logger",
]
