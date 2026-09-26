# quadkit/auth/providers/token_provider.py
"""Token management provider - handles JWT tokens only."""

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING, Annotated, Any

from quadkit.auth import constants as const
from quadkit.auth.authn.jwt import JWTTokenManager
from quadkit.contracts.core import (
    HealthCheckResult,
    HealthStatus,
    HookRegistryProtocol,
    ProviderPriority,
)
from quadkit.contracts.core.config import Environment
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
class TokenProvider(Provider):
    """JWT token management ONLY."""

    def __init__(
        self,
        config: Annotated[AuthConfig, Inject] | None = None,
        secret_key: str | None = None,
        jwt_algorithm: str | None = None,
        jwt_access_expiration_hours: int | None = None,
        jwt_refresh_expiration_days: int | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(name="tokens", priority=ProviderPriority.SECURITY)
        token_config = config.token if config else None

        # ── JWT verification policy ──────────────────────────────────────────
        # Verified-only decoding is enforced everywhere.  A missing secret is
        # fatal in PRODUCTION/STAGING; in DEVELOPMENT an ephemeral secret is
        # generated so signature verification never needs to be disabled.
        env = Environment.from_env()
        _STRICT_ENVS = {Environment.PRODUCTION, Environment.STAGING}

        # Secret resolution:
        # 1. Explicit secret_key argument → use it directly (verified mode).
        # 2. Config provided with a secret → use it (verified mode).
        # 3. Config provided but secret is absent → policy enforcement below.
        # 4. No config at all (config=None) → generate ephemeral secret (verified mode,
        #    zero-config dev/test usage documented in AuthModule.configure(None)).
        if secret_key:
            resolved_secret: str | None = secret_key
        elif token_config is not None:
            resolved_secret = (
                token_config.secret_key.get_secret_value()
                if token_config.secret_key
                else None
            )
        else:
            # No config at all: ephemeral key for zero-config dev/test.
            if env in _STRICT_ENVS:
                raise ConfigurationError(
                    f"CRITICAL SECURITY: JWT secret_key is required in {env.value.upper()} "
                    "but no AuthConfig was provided. "
                    "Set QK_AUTH__TOKEN__SECRET_KEY (or pass a configured AuthConfig)."
                )
            resolved_secret = secrets.token_urlsafe(32)
            logger.warning(
                "jwt_ephemeral_secret_generated",
                environment=env.value,
                reason="No AuthConfig supplied; using a generated ephemeral JWT secret. "
                "Tokens will be invalidated on restart. Provide a stable secret for production.",
            )

        if resolved_secret is None:
            # Config was provided but secret is absent — apply policy.
            if env in _STRICT_ENVS:
                raise ConfigurationError(
                    f"CRITICAL SECURITY: JWT secret_key is required in {env.value.upper()} "
                    "but none was provided. "
                    "Set QK_AUTH__TOKEN__SECRET_KEY (or token.secret_key in config)."
                )
            resolved_secret = secrets.token_urlsafe(32)
            logger.warning(
                "jwt_ephemeral_secret_generated",
                environment=env.value,
                reason="No JWT secret configured; using a generated ephemeral JWT secret. "
                "Signature verification stays enabled. Tokens are invalidated on "
                "restart; set QK_AUTH__TOKEN__SECRET_KEY for stable dev secrets.",
            )

        self.secret_key: str = resolved_secret

        logger.info(
            "jwt_verification_policy_boot",
            environment=env.value,
            mode="verified_only",
        )
        # ── End JWT verification policy ──────────────────────────────────────

        self.jwt_algorithm = jwt_algorithm or (
            token_config.algorithm if token_config else const.DEFAULT_TOKEN_ALGORITHM
        )
        self.jwt_access_expiration_hours: int = int(
            jwt_access_expiration_hours
            or (  # type: ignore[arg-type]
                getattr(token_config, "access_expiration_hours", 1)
                if token_config
                else 1
            )
        )
        self.jwt_refresh_expiration_days: int = int(
            jwt_refresh_expiration_days
            or (  # type: ignore[arg-type]
                getattr(
                    token_config,
                    "refresh_expiration_days",
                    const.DEFAULT_REFRESH_TOKEN_EXPIRE_DAYS,
                )
                if token_config
                else const.DEFAULT_REFRESH_TOKEN_EXPIRE_DAYS
            )
        )
        self.jwt_key_rotation_grace_period_seconds: int = int(
            getattr(
                token_config,
                "key_rotation_grace_period_seconds",
                const.DEFAULT_JWT_KEY_ROTATION_GRACE_PERIOD_SECONDS,
            )
            if token_config
            else const.DEFAULT_JWT_KEY_ROTATION_GRACE_PERIOD_SECONDS
        )

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        """Register token services with the container."""
        # If RSA algorithm chosen and secret is not an RSA PEM, generate an ephemeral keypair
        keys_to_pass = None
        current_kid = None
        if self.jwt_algorithm.startswith("RS"):
            # If secret_key looks like a PEM private key, use it
            if self.secret_key and "-----BEGIN" in self.secret_key:
                keys_to_pass = {"default": {"private": self.secret_key}}
                current_kid = "default"
            else:
                # Generate ephemeral RSA keypair
                try:
                    from cryptography.hazmat.primitives import serialization
                    from cryptography.hazmat.primitives.asymmetric import rsa
                except (ImportError, ModuleNotFoundError):
                    raise RuntimeError(
                        "cryptography is required for RS algorithms (install cryptography)",
                    ) from None

                private_key = rsa.generate_private_key(
                    public_exponent=65537,
                    key_size=2048,
                )
                private_pem = private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption(),
                ).decode("utf-8")

                public_pem = (
                    private_key.public_key()
                    .public_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PublicFormat.SubjectPublicKeyInfo,
                    )
                    .decode("utf-8")
                )

                keys_to_pass = {
                    "default": {"private": private_pem, "public": public_pem},
                }
                current_kid = "default"

                logger.warning(
                    "TokenProvider: using generated ephemeral RSA keypair for RS algorithm; provide persistent keys for production",
                )

        # Initialize token manager with keys or legacy secret
        from pydantic import SecretStr

        if keys_to_pass is not None and current_kid is not None:
            self.token_manager = JWTTokenManager(
                current_key_id=current_kid,
                keys=keys_to_pass,  # type: ignore[arg-type]
                algorithm=self.jwt_algorithm,
                access_expiration_hours=self.jwt_access_expiration_hours,
                refresh_expiration_days=self.jwt_refresh_expiration_days,
                grace_period_seconds=self.jwt_key_rotation_grace_period_seconds,
            )
        else:
            current_key = (
                SecretStr(self.secret_key)
                if isinstance(self.secret_key, str)
                else self.secret_key
            )
            self.token_manager = JWTTokenManager(
                current_key_id="default",
                keys={"default": current_key},
                algorithm=self.jwt_algorithm,
                access_expiration_hours=self.jwt_access_expiration_hours,
                refresh_expiration_days=self.jwt_refresh_expiration_days,
                grace_period_seconds=self.jwt_key_rotation_grace_period_seconds,
            )

        # Register with container
        container.singleton(JWTTokenManager, lambda: self.token_manager)

        # Also bind TokenManagerProtocol. AuthModule.configure() declares this
        # in its exports=[...] list, but nothing bound a container key for the
        # protocol itself — only the concrete JWTTokenManager type — even
        # though JWTTokenManager structurally satisfies TokenManagerProtocol
        # (create_token/verify_token/refresh_token). Bind it so the export is
        # honest and resolvable by callers that depend on the protocol.
        from quadkit.contracts.auth import TokenManagerProtocol

        if not container.has(TokenManagerProtocol):
            container.singleton(TokenManagerProtocol, lambda: self.token_manager)

    async def boot(self, container: ContainerResolverProtocol) -> None:
        """Initialize token provider."""
        logger.info("TokenProvider started")
        hooks = await container.resolve_optional(HookRegistryProtocol)
        self.token_manager.set_hook_registry(hooks)

        # Token revocation needs a cache backend; none is available during
        # register(). Attach a deferred source over the root resolver so
        # ``logout_all_user_tokens`` works once cache providers have booted,
        # independent of provider ordering.
        if hasattr(self.token_manager, "set_blacklist_resolver"):
            self.token_manager.set_blacklist_resolver(container.resolve_optional)

    async def shutdown(self) -> None:
        """Shutdown token provider."""
        logger.info("TokenProvider shutdown")

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Check token provider health."""
        return HealthCheckResult(
            component=self.name,
            status=HealthStatus.HEALTHY,
            details={
                "service": "tokens",
                "algorithm": self.jwt_algorithm,
                "access_expiration_hours": self.jwt_access_expiration_hours,
                "refresh_expiration_days": self.jwt_refresh_expiration_days,
            },
        )


__all__ = [
    "TokenProvider",
    "logger",
]
