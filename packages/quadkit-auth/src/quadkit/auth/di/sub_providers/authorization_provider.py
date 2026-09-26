# quadkit/auth/providers/authorization_provider.py
"""Authorization provider - handles role-based access control and permissions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any, cast

from quadkit.auth.authz.service import AuthorizationService
from quadkit.contracts import (
    AuthorizerProtocol,
    HealthCheckResult,
    HealthStatus,
    ProviderPriority,
)
from quadkit.di.decorators import inject
from quadkit.di.markers import Inject
from quadkit.di.provider import Provider
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.auth.config import AuthConfig
    from quadkit.contracts.core.di import (
        ContainerRegistrarProtocol,
        ContainerResolverProtocol,
    )

logger = get_logger(__name__)


@inject
class AuthorizationProvider(Provider):
    """Role-based access control and permission management."""

    def __init__(
        self,
        config: Annotated[AuthConfig, Inject] | None = None,
        initial_roles: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(name="authorization", priority=ProviderPriority.SECURITY)
        self._config = config
        self.initial_roles = initial_roles or {}

    @property
    def auth_config(self) -> AuthConfig | None:
        return cast("AuthConfig | None", self._config)

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        """Register authorization services with the container."""
        ttl = (
            getattr(self.auth_config.rbac, "permission_cache_ttl", 300.0)
            if self.auth_config and self.auth_config.rbac
            else 300.0
        )
        auth_service = AuthorizationService(permission_cache_ttl=ttl)

        # Auto-consume roles from config if no explicit initial_roles provided.
        # This lets examples define roles in application.yaml instead of hand-seeding.
        roles_to_load = self.initial_roles
        if not roles_to_load and self.auth_config and self.auth_config.roles:
            # Convert AuthRoleConfig instances (or raw dicts from yaml) to
            # the dict format set_roles expects.
            roles_to_load = {}
            for name, role in self.auth_config.roles.items():
                if isinstance(role, dict):
                    # Raw dict from yaml parsing — AuthConfig didn't coerce
                    roles_to_load[name] = {
                        "name": name,
                        "permissions": role.get("permissions", []),
                        "inherits": role.get("inherits", []),
                    }
                else:
                    # AuthRoleConfig instance
                    roles_to_load[name] = {
                        "name": role.name,
                        "permissions": role.permissions,
                        "inherits": role.inherits,
                    }

        if roles_to_load:
            auth_service.set_roles(roles_to_load)

        container.singleton(AuthorizerProtocol, lambda: auth_service)
        container.singleton(AuthorizationService, lambda: auth_service)

        logger.info(
            "AuthorizationProvider registered with %d initial roles",
            len(roles_to_load),
        )

    async def boot(self, container: ContainerResolverProtocol) -> None:
        """Initialize authorization provider."""
        logger.info("AuthorizationProvider started")

    async def shutdown(self) -> None:
        """Shutdown authorization provider."""
        logger.info("AuthorizationProvider shutdown")

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Check authorization provider health."""
        return HealthCheckResult(
            component=self.name,
            status=HealthStatus.HEALTHY,
            details={
                "service": "authorization",
                "initial_roles_count": len(self.initial_roles),
            },
        )


__all__ = [
    "AuthorizationProvider",
    "logger",
]
