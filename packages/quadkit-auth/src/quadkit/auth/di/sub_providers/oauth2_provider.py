# quadkit/auth/providers/oauth2_provider.py
"""OAuth2 provider - handles OAuth2/OIDC integration only."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

from quadkit.auth.authn.oauth2 import (
    OAuth2IdentityProvider as OAuth2IdentityProviderConfig,
)
from quadkit.auth.authn.oauth2 import OAuth2Manager
from quadkit.contracts.core import HealthCheckResult, HealthStatus, ProviderPriority
from quadkit.di.decorators import inject
from quadkit.di.markers import Inject
from quadkit.di.provider import Provider
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.auth.config import AuthConfig
    from quadkit.auth.storage.oauth_identity_store import OAuthIdentityStore
    from quadkit.contracts.core.di import (
        ContainerRegistrarProtocol,
        ContainerResolverProtocol,
    )

logger = get_logger(__name__)


def _scope_value(value: Any) -> str:
    """Normalize string and sequence scope configuration for authlib."""
    if isinstance(value, (list, tuple, set)):
        return " ".join(str(item).strip() for item in value if str(item).strip())
    return str(value or "openid email profile").strip()


def _bool_value(value: Any, default: bool = True) -> bool:
    """Accept YAML booleans and legacy string booleans consistently."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


@inject
class OAuth2Provider(Provider):
    """OAuth2/OIDC integration ONLY."""

    def __init__(
        self,
        config: Annotated[AuthConfig, Inject] | None = None,
        oauth2_providers: dict[str, dict[str, Any]] | None = None,
        oauth_identity_store: OAuthIdentityStore | None = None,
        http_client: Any | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(name="oauth2", priority=ProviderPriority.SECURITY)
        self.oauth2_providers = oauth2_providers or (
            config.oauth2_providers if config else {}
        )
        self.oauth_identity_store: OAuthIdentityStore | None = oauth_identity_store
        self.http_client = http_client

    @property
    def identity_resolver(self) -> OAuthIdentityStore | None:
        """Return the OAuth identity store for resolving external IDs to internal UUIDs.

        This property exposes the OAuthIdentityStore which implements
        IdentityResolverProtocol for resolving OAuth external IDs.
        """
        return self.oauth_identity_store

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        """Register OAuth2 services with the container."""
        # Convert raw config dicts to OAuth2IdentityProviderConfig instances
        resolved_providers: dict[str, OAuth2IdentityProviderConfig] = {
            provider_name: OAuth2IdentityProviderConfig(
                name=provider_name,
                client_id=cfg.get("client_id", ""),
                client_secret=cfg.get("client_secret", ""),
                authorize_url=cfg.get("authorize_url", ""),
                access_token_url=cfg.get("access_token_url", ""),
                userinfo_url=cfg.get("userinfo_url", ""),
                scope=_scope_value(cfg.get("scope", "openid email profile")),
                redirect_uri=cfg.get("redirect_uri"),
                require_pkce=_bool_value(cfg.get("require_pkce"), default=True),
                auth_style=int(cfg.get("auth_style", 0) or 0),
            )
            for provider_name, cfg in self.oauth2_providers.items()
        }

        # OAuth2 manager
        oauth2_manager = OAuth2Manager(
            providers=resolved_providers,
            http_client=self.http_client,
        )
        container.singleton(OAuth2Manager, lambda: oauth2_manager)

        # Register OAuthIdentityStore for identity resolution
        # This enables resolving user IDs from OAuth external IDs
        from quadkit.auth.storage.oauth_identity_store import (
            OAuthIdentityStore,
        )

        container.singleton(OAuthIdentityStore, lambda: self.oauth_identity_store)

        # Register individual OAuth2 providers
        for name, cfg in self.oauth2_providers.items():
            provider = OAuth2IdentityProviderConfig(
                name=name,
                client_id=cfg.get("client_id", ""),
                client_secret=cfg.get("client_secret", ""),
                authorize_url=cfg.get("authorize_url", ""),
                access_token_url=cfg.get("access_token_url", ""),
                userinfo_url=cfg.get("userinfo_url", ""),
                scope=_scope_value(cfg.get("scope", "openid email profile")),
                redirect_uri=cfg.get("redirect_uri"),
                require_pkce=_bool_value(cfg.get("require_pkce"), default=True),
                auth_style=int(cfg.get("auth_style", 0) or 0),
            )
            container.singleton(f"oauth2.{name}", lambda p=provider: p)

    async def boot(self, container: ContainerResolverProtocol) -> None:
        """Initialize OAuth2 provider."""
        logger.info("OAuth2Provider started")

    async def shutdown(self) -> None:
        """Shutdown OAuth2 provider."""
        logger.info("OAuth2Provider shutdown")

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Check OAuth2 provider health."""
        return HealthCheckResult(
            component=self.name,
            status=HealthStatus.HEALTHY,
            details={
                "service": "oauth2",
                "providers_count": len(self.oauth2_providers),
                "identity_store_type": type(self.oauth_identity_store).__name__,
            },
        )


__all__ = [
    "OAuth2Provider",
    "logger",
]
