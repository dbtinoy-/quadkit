"""DI wiring for the auth web demo.

A Provider tells the DI container *what* exists and *how* to build it.
Two-phase lifecycle: ``register()`` binds, ``boot()`` initializes.
"""

from __future__ import annotations

from auth_web.config import AuthWebConfig
from auth_web.controllers.api import AuthApiController
from auth_web.data.seed import DemoSeedService
from auth_web.repository import InMemorySessionRepository
from auth_web.services.account_verification import DemoAccountVerificationService
from auth_web.services.password_change import PasswordChangeService
from auth_web.services.password_reset import DemoPasswordResetService
from auth_web.ui.pages import PagesController
from quadkit.auth import (
    AuthConfig,
    AuthenticationService,
    SessionCookieBackend,
    UserService,
)
from quadkit.auth.authz import AuthorizationService
from quadkit.contracts.auth import (
    PasswordHasherProtocol,
    SessionRepositoryProtocol,
)
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


class AuthWebProvider(Provider):
    """Demo-specific DI registrations — your app replaces this.

    Provider lifecycle: register() → boot() → shutdown().
    register() binds services (no I/O); boot() initializes after freeze.
    """

    name = "auth-web"
    config_key: str | None = "auth_web"
    config_model: type | None = AuthWebConfig

    def __init__(self, config: AuthWebConfig | None = None) -> None:
        super().__init__()
        self._config = config

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        """Bind demo services — no I/O here."""
        if self._config is None:
            self._config = AuthWebConfig()
        container.singleton(AuthWebConfig, instance=self._config)

        # --- Stores: trivial objects, bind as instances ---
        repository = InMemorySessionRepository()
        container.singleton(InMemorySessionRepository, instance=repository)
        container.singleton(SessionRepositoryProtocol, instance=repository)

        # --- Services that need auth dependencies: async factories ---
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
                secure=False,
            )

        async def build_password_changes(resolver):
            authentication = await resolver.resolve(AuthenticationService)
            return PasswordChangeService(
                password_hasher=await resolver.resolve(PasswordHasherProtocol),
                policy=authentication.password_policy,
                user_store=authentication.user_store,
            )

        async def build_password_resets(resolver):
            authentication = await resolver.resolve(AuthenticationService)
            config = await resolver.resolve(AuthWebConfig)
            return DemoPasswordResetService(
                user_store=authentication.user_store,
                config=config.password_reset,
            )

        async def build_verification(resolver):
            authentication = await resolver.resolve(AuthenticationService)
            config = await resolver.resolve(AuthWebConfig)
            return DemoAccountVerificationService(
                user_store=authentication.user_store,
                config=config.account_verification,
            )

        async def build_api(resolver):
            return AuthApiController(
                authentication=await resolver.resolve(AuthenticationService),
                cookies=await resolver.resolve(SessionCookieBackend),
                sessions=await resolver.resolve(InMemorySessionRepository),
                authz=await resolver.resolve(AuthorizationService),
                password_changes=await resolver.resolve(PasswordChangeService),
                password_resets=await resolver.resolve(DemoPasswordResetService),
                verification=await resolver.resolve(DemoAccountVerificationService),
                config=await resolver.resolve(AuthWebConfig),
            )

        async def build_seed(resolver):
            return DemoSeedService(
                user_service=await resolver.resolve(UserService),
                config=await resolver.resolve(AuthConfig),
                authz=await resolver.resolve(AuthorizationService),
            )

        container.singleton(UserService, factory=build_users)
        container.singleton(SessionCookieBackend, factory=build_cookies)
        container.singleton(PasswordChangeService, factory=build_password_changes)
        container.singleton(DemoPasswordResetService, factory=build_password_resets)
        container.singleton(DemoAccountVerificationService, factory=build_verification)
        container.singleton(AuthApiController, factory=build_api)
        container.singleton(PagesController, instance=PagesController())
        container.singleton(DemoSeedService, factory=build_seed)

    async def boot(self, container: BootContainerProtocol) -> None:
        """Seed demo users and roles — I/O is allowed here."""
        seeder = await container.resolve(DemoSeedService)
        await seeder.run()

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Report readiness of this provider.

        Convention followed: **Provider pattern** — every provider exposes the
        uniform health contract (component / status / category) that the
        monitor-stack demo and ops tooling consume.
        """
        return HealthCheckResult(
            component=self.name,
            status=HealthStatus.HEALTHY,
            category=HealthCheckCategory.READINESS,
        )
