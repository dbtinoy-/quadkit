"""Convenience provider that registers the full authentication + authorisation stack.

Import and register :class:`AuthBundleProvider` when you want the complete
auth subsystem in a single line instead of adding four separate providers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Self

from quadkit.auth.config import AuthConfig
from quadkit.auth.di.sub_providers.admin_provider import AuthAdminProvider
from quadkit.auth.di.sub_providers.authentication_provider import (
    AuthenticationProvider,
)
from quadkit.auth.di.sub_providers.authorization_provider import AuthorizationProvider
from quadkit.auth.di.sub_providers.google_oauth_provider import GoogleOAuthProvider
from quadkit.auth.di.sub_providers.mfa_provider import MFAProvider
from quadkit.auth.di.sub_providers.session_provider import SessionProvider
from quadkit.auth.di.sub_providers.token_provider import TokenProvider
from quadkit.contracts.core import HealthCheckResult, HealthStatus, ProviderPriority
from quadkit.di.provider import Provider
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.contracts.core.di import (
        BootContainerProtocol,
        ContainerRegistrarProtocol,
    )

logger = get_logger(__name__)

__all__ = ["AuthBundleProvider"]


class AuthBundleProvider(Provider):
    """Composite provider that wires the full Quadkit auth stack.

    Composes :class:`~quadkit.auth.di.AuthenticationProvider`,
    :class:`~quadkit.auth.di.sub_providers.token_provider.TokenProvider`,
    :class:`~quadkit.auth.di.sub_providers.session_provider.SessionProvider`,
    and :class:`~quadkit.auth.di.AuthorizationProvider` so that callers only
    need to register a single provider:

    .. code-block:: python

        container.add_provider(AuthBundleProvider(config=auth_config))

    Dependencies registered by each sub-provider are available in the
    container after :meth:`register` completes.

    Args:
        config: Shared :class:`~quadkit.auth.config.AuthConfig` forwarded to
            every sub-provider.  When ``None``, each sub-provider uses its own
            defaults.
        initial_roles: Optional initial RBAC roles forwarded to
            :class:`~quadkit.auth.di.AuthorizationProvider`.
        enable_passkeys: When ``True``, append
            :class:`~quadkit.auth.di.sub_providers.passkey_provider.PasskeyProvider`
            to the sub-provider list (requires the WebAuthn extra to be
            installed).
        kwargs: Extra keyword arguments forwarded to
            :class:`~quadkit.auth.di.AuthenticationProvider`.
    """

    config_key: str | None = "auth"
    config_model: type | None = AuthConfig

    def __init__(
        self,
        config: AuthConfig | None = None,
        initial_roles: dict[str, Any] | None = None,
        enable_passkeys: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(name="auth_bundle", priority=ProviderPriority.SECURITY)
        self._config = config
        # Explicit config must win over the orchestrator's ``auth`` yaml
        # section injection (e.g. ``AuthModule.stub()`` / ``configure()``).
        # When no config was supplied the yaml section is still injected at
        # register() time by ``_inject_provider_config``.
        self._config_from_factory = config is not None
        self._initial_roles: dict[str, Any] = initial_roles or {}
        self._enable_passkeys = enable_passkeys
        self._sub_providers: list[Provider] = []
        if config is not None:
            # Explicit config: compose eagerly (no ephemeral-secret noise).
            # Zero-config construction defers to register(), after the
            # orchestrator has injected the yaml section.
            self._compose_sub_providers()

    def _compose_sub_providers(self) -> None:
        """(Re)build sub-providers from the current ``self._config``.

        Called from ``__init__`` and again lazily in ``register()`` when the
        orchestrator injected the yaml section after construction (i.e.
        ``configure()`` ran with no explicit config). Recomposition before
        any ``register()`` call is safe — nothing has been registered yet.
        """
        cfg = self._config
        self._authn = AuthenticationProvider(config=cfg)
        self._token = TokenProvider(config=cfg)
        self._session = SessionProvider(config=cfg)
        self._authz = AuthorizationProvider(
            config=cfg, initial_roles=dict(self._initial_roles)
        )
        self._admin = AuthAdminProvider(config=cfg)
        self._mfa = MFAProvider(config=cfg)
        self._sub_providers = [
            self._authn,
            self._token,
            self._session,
            self._authz,
            self._admin,
            self._mfa,
        ]
        google_oauth_config = (
            getattr(cfg, "oauth2_providers", {}).get("google", {})
            if cfg is not None
            else {}
        )
        if google_oauth_config:
            self._sub_providers.append(
                GoogleOAuthProvider(config=cfg, google_oauth=google_oauth_config),
            )
        if self._enable_passkeys:
            try:
                from quadkit.auth.di.sub_providers.passkey_provider import (
                    PasskeyProvider,
                )

                self._sub_providers.append(PasskeyProvider(config=cfg))
            except ImportError:
                logger.warning(
                    "auth.passkeys_unavailable",
                    reason="PasskeyProvider could not be imported",
                )

    @classmethod
    def from_config(cls, config: AuthConfig, **context: Any) -> Self:
        """Create provider from config object."""
        return cls(config=config)

    # ------------------------------------------------------------------
    # Provider interface
    # ------------------------------------------------------------------

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        """Register all auth sub-providers with the container.

        Late config binding: the orchestrator injects the typed ``auth``
        section (via ``config_key``) after construction and before this call.
        If ``configure()`` ran with no explicit config, recompose now so the
        automatic path behaves identically to the explicit one.

        Args:
            container: The DI container registrar.
        """
        if not self._sub_providers:
            # Zero-config construction is a documented dev/test mode
            # (TokenProvider generates an ephemeral secret).
            self._compose_sub_providers()
        elif any(sp.config is None for sp in self._sub_providers):
            # Late-injected yaml section (configure() ran without explicit
            # config): recompose so sub-providers hold the real values.
            self._compose_sub_providers()
        for provider in self._sub_providers:
            await provider.register(container)

        # Register AuthConfig so application code (e.g. seed services)
        # can resolve it from the container without manual wiring.
        if self._config is not None:
            container.singleton(AuthConfig, instance=self._config)

        logger.info("auth_bundle.registered")

    async def boot(self, container: BootContainerProtocol) -> None:
        """Boot all auth sub-providers in registration order.

        Args:
            container: The DI container resolver.
        """
        for provider in self._sub_providers:
            await provider.boot(container)
        logger.info("auth_bundle.booted")

    async def shutdown(self) -> None:
        """Shut down all auth sub-providers in reverse registration order."""
        for provider in reversed(self._sub_providers):
            await provider.shutdown()
        logger.info("auth_bundle.shutdown")

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Aggregate health check across all sub-providers.

        Returns :attr:`~quadkit.contracts.core.HealthStatus.DEGRADED` if any
        sub-provider is unhealthy.

        Args:
            timeout: Per-provider timeout budget in seconds.

        Returns:
            An aggregated :class:`~quadkit.contracts.core.HealthCheckResult`.
        """
        results = [await p.health_check(timeout=timeout) for p in self._sub_providers]
        overall = (
            HealthStatus.HEALTHY
            if all(r.status == HealthStatus.HEALTHY for r in results)
            else HealthStatus.DEGRADED
        )
        return HealthCheckResult(
            component=self.name,
            status=overall,
            details={r.component: r.status.value for r in results},
        )
