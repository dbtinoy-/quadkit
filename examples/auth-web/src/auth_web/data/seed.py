"""One-shot demo data seeding for the auth web demo.

Consumes ``AuthConfig.users`` from ``application.yaml`` — no hardcoded
user data.  Framework services return ``Result`` values, so seeding
handles the "already exists" case by matching on the error.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from quadkit.auth import UserService
from quadkit.auth.authz import AuthorizationService
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.auth.config import AuthConfig

logger = get_logger(__name__)


class DemoSeedService:
    """Seed demo users and RBAC roles from AuthConfig exactly once.

    Constructed by AuthWebProvider during boot; all collaborators arrive
    via constructor injection.
    """

    def __init__(
        self,
        user_service: UserService,
        config: AuthConfig,
        authz: AuthorizationService,
    ) -> None:
        self._user_service = user_service
        self._config = config
        self._authz = authz

    async def run(self) -> None:
        """Create users from AuthConfig.users and install role definitions."""
        for user_cfg in self._config.users:
            created = await self._user_service.create_user(
                name=user_cfg.name,
                email=user_cfg.email,
                password=user_cfg.password or "changeme",
                roles=user_cfg.roles,
            )
            if created.is_err():
                logger.info("seed_user_present", email=user_cfg.email)

        if self._config.roles:
            self._authz.set_roles(self._config.roles)


__all__ = ["DemoSeedService"]
