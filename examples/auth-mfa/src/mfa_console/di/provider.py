"""DI wiring for the MFA console demo.

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

from mfa_console.config import MfaConsoleConfig
from mfa_console.controllers.api import MfaApiController
from mfa_console.data.seed import MfaSeedService
from mfa_console.repository.session_repository import InMemorySessionRepository
from mfa_console.ui.pages import PagesController
from quadkit.auth import AuthenticationService, SessionCookieBackend, UserService
from quadkit.auth.config import AuthConfig
from quadkit.auth.mfa.manager import MFAManager
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


class MfaProvider(Provider):
    """Demo-specific DI registrations — your app replaces this.

    Provider lifecycle: register() → boot() → shutdown().
    register() binds services (no I/O); boot() initializes after freeze.
    """

    name = "mfa-console"
    config_key: str | None = "mfa_console"
    config_model: type | None = MfaConsoleConfig

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        """Bind demo services — no I/O here.

        ``container.singleton(Thing, instance=Thing())`` for already-built objects.
        ``container.singleton(Thing, factory=async_fn)`` for services that need
        other services resolved first (async factories run during resolve).
        """
        cfg = self.config or MfaConsoleConfig()
        container.singleton(MfaConsoleConfig, instance=cfg)

        # --- Repositories: in-memory stores, bind as instances ---
        # Dual-binding: register both the concrete type AND the protocol.
        # Framework code resolves contracts; your code resolves concrete types.
        repository = InMemorySessionRepository()
        container.singleton(InMemorySessionRepository, instance=repository)
        container.singleton(SessionRepositoryProtocol, instance=repository)

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
                session_repository=await resolver.resolve(SessionRepositoryProtocol),
                user_fetcher=(await resolver.resolve(UserService)).get_user,
                secure=False,  # local demo runs plain http
            )

        async def build_seed(resolver):
            return MfaSeedService(
                users=await resolver.resolve(UserService),
                config=await resolver.resolve(AuthConfig),
            )

        container.singleton(UserService, factory=build_users)
        container.singleton(SessionCookieBackend, factory=build_cookies)
        container.singleton(MfaSeedService, factory=build_seed)

        # --- Demo-specific: controller ---
        # Controllers receive all collaborators via constructor injection.
        # The framework resolves the controller when a request matches its routes.
        async def build_api(resolver):
            return MfaApiController(
                authentication=await resolver.resolve(AuthenticationService),
                users=await resolver.resolve(UserService),
                mfa=await resolver.resolve(MFAManager),
                cookies=await resolver.resolve(SessionCookieBackend),
                sessions=await resolver.resolve(InMemorySessionRepository),
                config=await resolver.resolve(AuthConfig),
            )

        container.singleton(MfaApiController, factory=build_api)
        container.singleton(PagesController, factory=PagesController)

    async def boot(self, container: BootContainerProtocol) -> None:
        """Seed users and enroll the MFA persona — I/O is allowed here.

        boot() runs AFTER register() completes and the container is frozen.
        This is where you resolve services and do initialization work
        (seeding data, warming caches, connecting to external services).
        """
        seeder = await container.resolve(MfaSeedService)
        await seeder.run()

        users = await container.resolve(UserService)
        mfa = await container.resolve(MFAManager)
        auth_config = await container.resolve(AuthConfig)

        # Find the user to enroll for MFA from the yaml config.
        # The second user in auth.users is the MFA candidate — no hardcoded
        # email.  If no users are configured, enrollment is skipped.
        if auth_config.users and len(auth_config.users) > 1:
            mfa_email = auth_config.users[1].email
            mfa_user = await users.user_store.get_user_by_email(mfa_email)
            if mfa_user is not None:
                profile_mfa = (mfa_user.profile or {}).get("mfa") or {}
                if not profile_mfa.get("enabled"):
                    await mfa.enable_totp(mfa_user.user_id, issuer="auth-mfa-demo")

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Report readiness of this provider.

        Convention followed: **Provider pattern** — every provider exposes the
        uniform health contract (component / status / category) that the
        monitor-stack demo and ops tooling consume.
        """
        cfg = self.config or MfaConsoleConfig()
        return HealthCheckResult(
            component=self.name,
            status=HealthStatus.HEALTHY,
            category=HealthCheckCategory.READINESS,
            message=f"{cfg.service_name} provider ready",
        )
