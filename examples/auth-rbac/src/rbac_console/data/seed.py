"""Boot-time demo seeding — users and starter articles.

Consumes ``AuthConfig.users`` from ``application.yaml`` — no hardcoded
user data.  This pattern replaces hand-seeding: define users in yaml,
and the seed service creates them at boot.

Framework services return ``Result`` values
(``UserService.create_user`` → ``Ok``/``Err``), so seeding handles the
"already exists" case by matching on the error instead of pre-checking.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from quadkit.auth import UserService
from quadkit.logging import get_logger
from rbac_console.domain.articles import ArticleStore
from rbac_console.domain.personas import PERSONAS, PersonaDirectory

if TYPE_CHECKING:
    from quadkit.auth.config import AuthConfig

logger = get_logger(__name__)


class RbacSeedService:
    """Seed users from AuthConfig.users and starter articles.

    Constructed by RbacProvider during boot; all collaborators arrive
    via constructor injection.  This is a one-shot initializer, not a
    runtime service — it lives in ``data/`` because it's data setup.

    Your app replaces this with your own seeding logic (database
    migrations, fixture files, etc.).
    """

    def __init__(
        self,
        users: UserService,
        config: AuthConfig,
        personas: PersonaDirectory,
        articles: ArticleStore,
    ) -> None:
        self._users = users
        self._config = config
        self._personas = personas
        self._articles = articles

    async def run(self) -> None:
        """Create users from AuthConfig.users and add starter articles.

        Notice the Result handling: ``create_user`` returns ``Result[User, ...]``.
        On first boot it's ``Ok``; on subsequent boots it's ``Err(duplicate)``.
        The seeder doesn't pre-check — it just matches on the error type.
        """
        for user_cfg in self._config.users:
            # create_user returns Result[User, ...]: Ok on first run,
            # Err(duplicate) on every later boot — both are fine here.
            created = await self._users.create_user(
                name=user_cfg.name,
                email=user_cfg.email,
                password=user_cfg.password or "changeme",
                roles=user_cfg.roles,
            )
            if created.is_err():
                logger.info("seed_user_present", email=user_cfg.email)
            else:
                user = created.unwrap()
                # Register persona if role matches a known persona key
                for role in user_cfg.roles:
                    if role in PERSONAS:
                        self._personas.register(role, user)

        self._articles.create("Welcome", "Articles are guarded by RBAC patterns.")
        self._articles.create("Second", "Try creating one as different personas.")


__all__ = ["RbacSeedService"]
