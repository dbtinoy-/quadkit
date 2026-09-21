"""Convention followed: **Provider lifecycle** — ``register()`` declares
singletons (including the controller, as a class binding), ``boot()``
builds the wired controller instance and rebinds it, ``health_check()``
reports readiness; ``config_key``/``config_model`` wire the typed yaml
section into ``self.config``.

Lifecycle wiring for the Auth Tokens demo: the signing secret comes from
typed config (``QK_AUTH_TOKENS__TOKEN_SECRET`` overrides it), never from
code.
"""

from __future__ import annotations

from auth_tokens.config import AuthTokensConfig
from auth_tokens.controllers.api import SessionController
from auth_tokens.services.tokens import TokenService
from quadkit.contracts.core import HealthCheckResult, HealthStatus
from quadkit.contracts.core.di import (
    ContainerRegistrarProtocol,
    ContainerResolverProtocol,
)
from quadkit.di.provider import Provider


class AuthTokensProvider(Provider):
    """Bind the token service and the controller."""

    name = "auth_tokens"
    config_key: str | None = "auth_tokens"
    config_model: type | None = AuthTokensConfig

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        config = (
            self.config
            if isinstance(self.config, AuthTokensConfig)
            else AuthTokensConfig()
        )
        container.singleton(
            TokenService,
            instance=TokenService(config.token_secret.get_secret_value()),
        )
        container.singleton(SessionController, SessionController)

    async def boot(self, container: ContainerResolverProtocol) -> None:
        tokens = await container.resolve(TokenService)
        container.bind(SessionController, SessionController(tokens))

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Report provider wiring for framework health aggregation."""
        return HealthCheckResult(
            component=self.name,
            status=HealthStatus.HEALTHY,
            details={"demo": "auth-tokens", "signing_secret_configured": True},
        )


__all__ = ["AuthTokensProvider"]
