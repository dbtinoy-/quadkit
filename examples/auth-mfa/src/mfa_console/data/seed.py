"""Boot-time demo data seeding for the MFA console.

Consumes ``AuthConfig.users`` from ``application.yaml`` — no hardcoded
user data.  This pattern replaces hand-seeding: define users in yaml,
and the seed service creates them at boot.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from quadkit.auth import UserService
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.auth.config import AuthConfig

logger = get_logger(__name__)


class MfaSeedService:
    """Create users defined in ``AuthConfig.users`` at boot.

    Reads the user list from the yaml config and calls
    ``UserService.create_user()`` for each.  On subsequent boots,
    ``create_user`` returns ``Err(duplicate)`` — the seeder matches
    on the error instead of pre-checking.
    """

    def __init__(self, users: UserService, config: AuthConfig) -> None:
        self._users = users
        self._config = config

    async def run(self) -> None:
        """Create all users from AuthConfig.users."""
        for user_cfg in self._config.users:
            created = await self._users.create_user(
                name=user_cfg.name,
                email=user_cfg.email,
                password=user_cfg.password or "changeme",
                roles=user_cfg.roles,
            )
            if created.is_err():
                logger.info("seed_user_present", email=user_cfg.email)
            else:
                logger.info("seed_user_created", email=user_cfg.email)


__all__ = ["MfaSeedService"]
