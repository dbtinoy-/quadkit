"""DI wiring for the RBAC console demo.

A Provider tells the DI container *what* exists and *how* to build it.
Two-phase lifecycle: ``register()`` binds, ``boot()`` initializes.

Simplest patterns for new users:

- ``container.singleton(Thing, instance=Thing())`` — already built, hand it over
- ``container.singleton(Thing, factory=lambda: ...)`` — build lazily on first resolve
- ``container.singleton(Thing, factory=self._build_thing)`` — async factory for complex wiring

Don't re-register framework keys (e.g. ``AuthorizationService``) — the
auth bundle already owns them.
"""

from __future__ import annotations

from rbac_console.config import RbacConsoleConfig
from rbac_console.controllers.api import RbacApiController
from rbac_console.data.seed import RbacSeedService
from rbac_console.domain.articles import ArticleStore
from rbac_console.domain.personas import PersonaDirectory
from rbac_console.repository.session_repository import InMemorySessionRepository

from quadkit.auth import SessionCookieBackend, UserService
from quadkit.auth.authz import AuthorizationService
from quadkit.auth.config import AuthConfig
from quadkit.contracts.auth import SessionRepositoryProtocol
from quadkit.contracts.core.di import (
    BootContainerProtocol,
    ContainerRegistrarProtocol,
)
from quadkit.contracts.core.health import (
    HealthCheckCategory,
    HealthCheckResult,
    HealthStatus,
)
from quadkit.di.provider import Provider
from quadkit.logging import get_logger

logger = get_logger(__name__)


class RbacProvider(Provider):
    """Demo-specific DI registrations — your app replaces this.

    Provider lifecycle: register() → boot() → shutdown().
    register() binds services (no I/O); boot() initializes after freeze.
    """

    name = "rbac-console"
    config_key: str | None = "rbac_console"
    config_model: type | None = RbacConsoleConfig

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        """Bind demo services — no I/O here.

        ``container.singleton(Thing, instance=Thing())`` for already-built objects.
        ``container.singleton(Thing, factory=async_fn)`` for services that need
        other services resolved first (async factories run during resolve).
        """
        cfg = self.config or RbacConsoleConfig()
        container.singleton(RbacConsoleConfig, instance=cfg)

        # --- Stores: trivial objects, bind as instances ---
        # InMemorySessionRepository is bound as both its concrete type AND
        # the protocol — framework code resolves SessionRepositoryProtocol,
        # tests can import InMemorySessionRepository directly.
        repository = InMemorySessionRepository()
        container.singleton(InMemorySessionRepository, instance=repository)
        container.singleton(SessionRepositoryProtocol, instance=repository)
        # ArticleStore and PersonaDirectory are plain dataclasses with no
        # framework dependencies — register as instances for simplicity.
        container.singleton(ArticleStore, instance=ArticleStore())
        container.singleton(PersonaDirectory, instance=PersonaDirectory())

        # --- Services that need auth dependencies: async factories ---
        # These factories resolve framework services (AuthenticationService,
        # AuthorizationService) that the auth module owns.  Your app never
        # creates these directly — they come from AuthModule.configure().
        async def build_users(resolver):
            from quadkit.auth import AuthenticationService

            authn = await resolver.resolve(AuthenticationService)
            return UserService(
                password_policy=authn.password_policy,
                user_store=authn.user_store,
            )

        async def build_cookies(resolver):
            return SessionCookieBackend(
                session_repository=await resolver.resolve(InMemorySessionRepository),
                user_fetcher=(await resolver.resolve(UserService)).get_user,
                secure=False,
            )

        container.singleton(UserService, factory=build_users)
        container.singleton(SessionCookieBackend, factory=build_cookies)

        # --- Demo-specific: controller and seeder ---
        # Controllers receive all collaborators via constructor injection.
        # The framework resolves the controller when a request matches its routes.
        async def build_api(resolver):
            return RbacApiController(
                users=await resolver.resolve(UserService),
                authz=await resolver.resolve(AuthorizationService),
                cookies=await resolver.resolve(SessionCookieBackend),
                personas=await resolver.resolve(PersonaDirectory),
                articles=await resolver.resolve(ArticleStore),
            )

        async def build_seed(resolver):
            return RbacSeedService(
                users=await resolver.resolve(UserService),
                config=await resolver.resolve(AuthConfig),
                personas=await resolver.resolve(PersonaDirectory),
                articles=await resolver.resolve(ArticleStore),
            )

        container.singleton(RbacApiController, factory=build_api)
        container.singleton(RbacSeedService, factory=build_seed)

    async def boot(self, container: BootContainerProtocol) -> None:
        """Seed personas and articles — I/O is allowed here.

        boot() runs AFTER register() completes and the container is frozen.
        This is where you resolve services and do initialization work
        (seeding data, warming caches, connecting to external services).
        """
        seeder = await container.resolve(RbacSeedService)
        await seeder.run()

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Report readiness of this provider.

        Convention followed: **Provider pattern** — every provider exposes the
        uniform health contract (component / status / category) that the
        monitor-stack demo and ops tooling consume.
        """
        cfg = self.config or RbacConsoleConfig()
        return HealthCheckResult(
            component=self.name,
            status=HealthStatus.HEALTHY,
            category=HealthCheckCategory.READINESS,
            message=f"{cfg.service_name} provider ready",
        )
