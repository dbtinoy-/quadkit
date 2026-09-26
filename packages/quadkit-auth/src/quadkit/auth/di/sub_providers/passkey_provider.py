# quadkit/auth/providers/passkey_provider.py
"""Passkey provider - handles WebAuthn/Passkey support only."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.contracts.core import HealthCheckResult, HealthStatus, ProviderPriority
from quadkit.di.decorators import inject
from quadkit.di.provider import Provider
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.contracts.core.di import (
        ContainerRegistrarProtocol,
        ContainerResolverProtocol,
    )

logger = get_logger(__name__)


@inject
class PasskeyProvider(Provider):
    """WebAuthn/Passkey support ONLY."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(name="passkeys", priority=ProviderPriority.SECURITY)
        # Passkey-specific configuration would go here
        # For now, this is a placeholder structure

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        """Register passkey services with the container."""
        # Passkey services would be registered here
        # This is a simplified version - in practice you'd have PasskeyManager, WebAuthnService, etc.

    async def boot(self, container: ContainerResolverProtocol) -> None:
        """Initialize passkey provider."""
        logger.info("PasskeyProvider started")

    async def shutdown(self) -> None:
        """Shutdown passkey provider."""
        logger.info("PasskeyProvider shutdown")

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Check passkey provider health."""
        return HealthCheckResult(
            component=self.name,
            status=HealthStatus.HEALTHY,
            details={
                "service": "passkeys",
                "message": "Passkey provider placeholder - implement WebAuthn and FIDO2 support",
            },
        )


__all__ = [
    "PasskeyProvider",
    "logger",
]
