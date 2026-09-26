"""Google OAuth provider — first-class Google token verification support."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

from quadkit.auth.authn.google_oauth import (
    GOOGLE_ISSUERS,
    GOOGLE_JWKS_URL,
    GOOGLE_TOKENINFO_URL,
    GOOGLE_USERINFO_URL,
    GoogleOAuthService,
)
from quadkit.contracts.core import HealthCheckResult, HealthStatus, ProviderPriority
from quadkit.contracts.exceptions import ConfigurationError
from quadkit.di.decorators import inject
from quadkit.di.markers import Inject
from quadkit.di.provider import Provider
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.auth.config import AuthConfig
    from quadkit.contracts.core.di import (
        ContainerRegistrarProtocol,
        ContainerResolverProtocol,
    )

logger = get_logger(__name__)


@inject
class GoogleOAuthProvider(Provider):
    """Registers a first-class Google OAuth verification service."""

    def __init__(
        self,
        config: Annotated[AuthConfig, Inject] | None = None,
        google_oauth: dict[str, str] | None = None,
        http_client: Any | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(name="google_oauth", priority=ProviderPriority.SECURITY)
        self._config = google_oauth or (
            config.oauth2_providers.get("google", {}) if config else {}
        )
        self._http_client = http_client
        self._service: GoogleOAuthService | None = None

    @property
    def service(self) -> GoogleOAuthService | None:
        """Return the registered Google OAuth service, if any."""
        return self._service

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        """Register the Google OAuth verifier service."""
        client_id = self._config.get("client_id")
        if not client_id:
            raise ConfigurationError(
                "Google OAuth configuration is missing client_id; set "
                "auth.oauth2_providers.google.client_id or pass google_oauth={...}"
            )

        jwks_url = self._config.get("jwks_url") or None
        tokeninfo_url = self._config.get("tokeninfo_url") or None
        userinfo_url = self._config.get("userinfo_url") or None
        issuer_values = self._config.get("issuer") or self._config.get("issuers")
        allowed_issuers: tuple[str, ...]
        if isinstance(issuer_values, str):
            allowed_issuers = (issuer_values,)
        elif isinstance(issuer_values, list):
            allowed_issuers = tuple(str(value) for value in issuer_values if value)
        else:
            allowed_issuers = ()

        jwks_cache_ttl_seconds = int(self._config.get("jwks_cache_ttl_seconds", 300))

        service = GoogleOAuthService(
            client_id=client_id,
            http_client=self._http_client,
            jwks_url=jwks_url or GOOGLE_JWKS_URL,
            tokeninfo_url=tokeninfo_url or GOOGLE_TOKENINFO_URL,
            userinfo_url=userinfo_url or GOOGLE_USERINFO_URL,
            allowed_issuers=allowed_issuers or GOOGLE_ISSUERS,
            jwks_cache_ttl_seconds=jwks_cache_ttl_seconds,
        )
        self._service = service
        container.singleton(GoogleOAuthService, lambda: service)
        logger.info(
            "google_oauth.registered",
            configured=True,
            client_id_present=bool(client_id),
        )

    async def boot(self, container: ContainerResolverProtocol) -> None:
        """Initialize Google OAuth support."""
        logger.info("GoogleOAuthProvider started")

    async def shutdown(self) -> None:
        """Shutdown Google OAuth support."""
        logger.info("GoogleOAuthProvider shutdown")

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Check Google OAuth provider health."""
        configured = self._service is not None
        return HealthCheckResult(
            component=self.name,
            status=HealthStatus.HEALTHY if configured else HealthStatus.DEGRADED,
            details={
                "service": "google_oauth",
                "configured": configured,
                "client_id_present": bool(self._config.get("client_id")),
                "jwks_url": self._config.get("jwks_url")
                or "https://www.googleapis.com/oauth2/v3/certs",
                "userinfo_url": self._config.get("userinfo_url")
                or "https://www.googleapis.com/oauth2/v3/userinfo",
            },
        )


__all__ = ["GoogleOAuthProvider"]
