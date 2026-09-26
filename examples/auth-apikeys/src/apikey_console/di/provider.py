"""DI wiring for the api-keys demo — Provider lifecycle pattern.

A Provider tells the DI container *what* exists and *how* to build it.
Two-phase lifecycle: ``register()`` binds, ``boot()`` initializes.

Simplest patterns for new users:

- ``container.singleton(Thing, instance=Thing())`` — already built, hand it over
- ``container.singleton(Thing, factory=lambda: ...)`` — build lazily on first resolve
- ``container.singleton(Thing, factory=self._build_thing)`` — async factory for complex wiring

Don't re-register framework keys (e.g. ``AuthenticationService``) — the
auth bundle already owns them.
"""

from __future__ import annotations

from apikey_console.config import ApikeyConsoleConfig
from apikey_console.controllers.api import KeysApiController
from apikey_console.data.seed import DemoSeedService
from apikey_console.repository.keys_repository import InMemoryAPIKeyRepository
from apikey_console.repository.session_repository import InMemorySessionRepository
from apikey_console.ui.pages import PagesController
from quadkit.auth import (
    AuthenticationService,
    SessionCookieBackend,
    UserService,
)
from quadkit.auth.authn.apikeys import APIKeyManager
from quadkit.auth.config import AuthConfig
from quadkit.contracts.auth import APIKeyRepositoryProtocol, SessionRepositoryProtocol
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


class ApiKeysProvider(Provider):
    """Demo-specific DI registrations — your app replaces this.

    Provider lifecycle: register() → boot() → shutdown().
    register() binds services (no I/O); boot() initializes after freeze.
    """

    name = "apikeys-console"
    config_key: str | None = "apikey_console"
    config_model: type | None = ApikeyConsoleConfig

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        """Bind demo services — no I/O here.

        ``container.singleton(Thing, instance=Thing())`` for already-built objects.
        ``container.singleton(Thing, factory=async_fn)`` for services that need
        other services resolved first (async factories run during resolve).
        """
        cfg = self.config or ApikeyConsoleConfig()
        container.singleton(ApikeyConsoleConfig, instance=cfg)

        # --- Repositories: in-memory stores, bind as instances ---
        # Dual-binding: register both the concrete type AND the protocol.
        # Framework code resolves contracts; your code resolves concrete types.
        session_repo = InMemorySessionRepository()
        container.singleton(InMemorySessionRepository, instance=session_repo)
        container.singleton(SessionRepositoryProtocol, instance=session_repo)

        keys_repo = InMemoryAPIKeyRepository()
        container.singleton(InMemoryAPIKeyRepository, instance=keys_repo)
        container.singleton(APIKeyRepositoryProtocol, instance=keys_repo)

        # --- Services that need auth dependencies: async factories ---
        # These factories resolve framework services (AuthenticationService)
        # that the auth module owns.  Your app never creates these directly
        # — they come from AuthModule.configure().
        async def build_users(resolver):
            authn = await resolver.resolve(AuthenticationService)
            return UserService(
                password_policy=authn.password_policy,
                user_store=authn.user_store,
            )

        async def build_cookies(resolver):
            return SessionCookieBackend(
                session_repository=await resolver.resolve(InMemorySessionRepository),
                user_fetcher=(await resolver.resolve(UserService)).get_user,
                secure=False,  # local demo runs plain http
            )

        async def build_api_key_manager(resolver):
            return APIKeyManager(repo=keys_repo)

        container.singleton(UserService, factory=build_users)
        container.singleton(SessionCookieBackend, factory=build_cookies)
        container.singleton(APIKeyManager, factory=build_api_key_manager)

        # --- Demo-specific: controller and seeder ---
        # Controllers receive all collaborators via constructor injection.
        # The framework resolves the controller when a request matches its routes.
        async def build_api(resolver):
            return KeysApiController(
                authentication=await resolver.resolve(AuthenticationService),
                cookies=await resolver.resolve(SessionCookieBackend),
                manager=await resolver.resolve(APIKeyManager),
            )

        async def build_seed(resolver):
            return DemoSeedService(
                users=await resolver.resolve(UserService),
                config=await resolver.resolve(AuthConfig),
            )

        container.singleton(KeysApiController, factory=build_api)
        container.singleton(PagesController, factory=PagesController)
        container.singleton(DemoSeedService, factory=build_seed)

    async def boot(self, container: BootContainerProtocol) -> None:
        """Seed users from AuthConfig.users — I/O is allowed here.

        boot() runs AFTER register() completes and the container is frozen.
        This is where you resolve services and do initialization work
        (seeding data, warming caches, connecting to external services).
        """
        seeder = await container.resolve(DemoSeedService)
        await seeder.run()

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Report readiness of this provider.

        Convention followed: **Provider pattern** — every provider exposes the
        uniform health contract (component / status / category) that the
        monitor-stack demo and ops tooling consume.
        """
        cfg = self.config or ApikeyConsoleConfig()
        return HealthCheckResult(
            component=self.name,
            status=HealthStatus.HEALTHY,
            category=HealthCheckCategory.READINESS,
            message=f"{cfg.service_name} provider ready",
        )
