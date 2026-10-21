"""Authentication provider - handles user authentication only."""

from __future__ import annotations

import contextlib
import secrets
from typing import TYPE_CHECKING, Annotated, Any, cast

from pydantic import SecretStr

from quadkit.auth.authn.password_hasher import (
    Argon2idKeyDerivation,
    Argon2idPasswordHasher,
    ComposedPasswordHasher,
)
from quadkit.auth.authn.security import PasswordHasher, PasswordPolicy
from quadkit.auth.authn.services import AuthenticationService
from quadkit.auth.storage.token_store import InMemoryUserStore, UserStoreProtocol
from quadkit.contracts import HealthCheckResult, HealthStatus, ProviderPriority
from quadkit.contracts.auth import PasswordHasherProtocol, PasswordPolicyProtocol
from quadkit.contracts.core import HookRegistryProtocol
from quadkit.contracts.core.config import Environment
from quadkit.contracts.exceptions import ConfigurationError
from quadkit.di.markers import Inject
from quadkit.di.provider import Provider
from quadkit.logging import get_logger

__all__ = ["AuthenticationProvider"]


from quadkit.result import Err, Result

if TYPE_CHECKING:
    from quadkit.auth.config import AuthConfig
    from quadkit.auth.mfa.manager import MFAManager
    from quadkit.contracts.auth.exceptions import TokenError
    from quadkit.contracts.auth.token import VerifiedToken
    from quadkit.contracts.core.di import (
        BootContainerProtocol,
        ContainerRegistrarProtocol,
    )

logger = get_logger(__name__)


def _build_token_manager(
    secret_key: str | None,
    jwt_algorithm: str,
    cache_service: Any,
    required_audience: str | None = None,
) -> Any:
    """Build a JWTTokenManager from the supplied credentials.

    Generates an ephemeral RSA keypair when ``jwt_algorithm`` is RS-family
    and no PEM key is provided via ``secret_key``.

    Args:
        secret_key: HMAC secret or PEM-encoded RSA private key.
        jwt_algorithm: JWT signing algorithm (e.g. "HS256", "RS256").
        cache_service: Optional cache backend for token blacklisting.
        required_audience: Forwarded to :class:`JWTTokenManager`; when set,
            every verified token must carry a matching ``aud`` claim.

    Returns:
        A configured :class:`~quadkit.auth.authn.jwt.JWTTokenManager`.
    """
    from quadkit.auth.authn.jwt import JWTTokenManager

    if jwt_algorithm.startswith(("RS", "PS")):
        if secret_key and "-----BEGIN" in secret_key:
            keys: dict[str, Any] = {"default": {"private": secret_key}}
        else:
            try:
                from cryptography.hazmat.primitives import serialization
                from cryptography.hazmat.primitives.asymmetric import rsa
            except (ImportError, ModuleNotFoundError) as exc:
                raise RuntimeError(
                    "cryptography is required for RS/PS algorithms"
                ) from exc

            private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
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
            keys = {
                "default": {
                    "private": SecretStr(private_pem),
                    "public": SecretStr(public_pem),
                }
            }
            logger.warning(
                "AuthenticationProvider: generated ephemeral RSA keypair; "
                "provide persistent keys in production",
            )
        return JWTTokenManager(
            current_key_id="default",
            keys=keys,
            algorithm=jwt_algorithm,
            cache_service=cache_service,
            required_audience=required_audience,
        )

    # Symmetric algorithm: use secret_key directly (single-secret mode)
    env = Environment.from_env()
    _STRICT_ENVS = {Environment.PRODUCTION, Environment.STAGING}
    if not secret_key:
        if env in _STRICT_ENVS:
            raise ConfigurationError(
                f"CRITICAL SECURITY: JWT secret_key is required in {env.value.upper()} "
                "but none was provided. "
                "Set QK_AUTH__TOKEN__SECRET_KEY (or token.secret_key in config)."
            )
        effective_secret = secrets.token_urlsafe(32)
        logger.warning(
            "jwt_ephemeral_secret_generated",
            environment=env.value,
            reason="No JWT secret_key provided; using a generated ephemeral secret. "
            "Tokens will be invalidated on restart. Provide a stable secret for production.",
        )
    else:
        effective_secret = secret_key
    return JWTTokenManager(
        current_key_id="default",
        keys={"default": SecretStr(effective_secret)},
        algorithm=jwt_algorithm,
        cache_service=cache_service,
        required_audience=required_audience,
    )


def _resolve_default_cache_sync(container: Any) -> Any:
    """Deferred best-effort lookup of the application default cache.

    Auth boots before cache providers, so this runs lazily via
    ``set_blacklist_resolver``.  Returns ``None`` while no cache backend
    is registered; the blacklist manager treats ``None`` as "no durable
    store yet" and asks again on the next revocation.

    The container's ``resolve`` is a coroutine on every Quadkit container,
    so the awaitable is **returned** for the (async) blacklist to await —
    an earlier revision returned ``None`` in that case, which meant no
    application ever got a durable blacklist through this path.
    """
    if container is None or not hasattr(container, "resolve"):
        return None
    try:
        from quadkit.contracts.infra.cache import CacheBackendProtocol

        return container.resolve(CacheBackendProtocol)
    except Exception:  # noqa: BLE001 — cache subsystem may not exist yet
        return None


class AuthenticationProvider(Provider):
    """User authentication ONLY (login/logout/validation).

    ``config`` is the primary parameter and drives all defaults.  The optional
    keyword arguments are *override points* for callers that need to supply
    custom implementations (e.g., a production-grade :class:`UserStoreProtocol` backed
    by a database, or a pre-built token manager).

    Args:
        config: The resolved :class:`~quadkit.auth.config.AuthConfig`.
            JWT credentials (``config.token.secret_key``, ``config.token.algorithm``)
            are used to build a :class:`~quadkit.auth.authn.jwt.JWTTokenManager`
            automatically when no ``token_manager`` override is provided.
        password_policy: Override the password policy derived from ``config.password``.
            When *None* the policy is built from config; falls back to ``PasswordPolicy()``
            when config is also absent.
        user_store: Override the user store.  Defaults to :class:`InMemoryUserStore`.
        token_manager: Supply a fully constructed token manager.  When *None* and
            ``config.token`` is present the manager is built automatically from the
            JWT configuration.
        cache_service: Optional cache backend passed to the auto-built token manager
            for token blacklisting.  Ignored when ``token_manager`` is provided directly.
        mfa_service: Optional MFA manager for multi-factor authentication flows.
    """

    def __init__(
        self,
        config: Annotated[AuthConfig, Inject] | None = None,
        *,
        password_policy: PasswordPolicy | None = None,
        user_store: UserStoreProtocol | None = None,
        token_manager: Any = None,
        cache_service: Any = None,
        mfa_service: MFAManager | None = None,
    ) -> None:
        super().__init__(name="authentication", priority=ProviderPriority.SECURITY)
        self._config = config
        if password_policy is not None:
            self.password_policy = password_policy
        elif config is not None and config.password is not None:
            self.password_policy = PasswordPolicy.from_config(config.password)
        else:
            self.password_policy = PasswordPolicy()
        self.user_store = user_store or InMemoryUserStore()
        self.mfa_service = mfa_service

        # Auto-create a JWTTokenManager from config when no override is supplied.
        if (
            token_manager is None
            and config is not None
            and getattr(config, "token", None) is not None
        ):
            token_manager = _build_token_manager(
                secret_key=config.token.secret_key.get_secret_value(),
                jwt_algorithm=config.token.algorithm,
                cache_service=cache_service,
                required_audience=config.token.required_audience,
            )

        self.token_manager = token_manager
        self.delegation_manager: Any = None
        # AuthProviderProtocol declares these as "Optional managers — None
        # when the feature is disabled/not configured" (see
        # quadkit.contracts.auth.protocols.AuthProviderProtocol). Before this
        # fix only delegation_manager followed that contract; the other three
        # were simply never set, so any code accessing them (e.g.
        # SessionAuthenticator, ApiKeyAuthenticator, the MFA guard decorator
        # in AuthMiddleware) raised AttributeError instead of gracefully
        # treating the feature as disabled. boot() below upgrades
        # session_manager/api_key_manager to the real sibling-provider
        # instances when those providers are present in the same container.
        self.session_manager: Any = None
        self.api_key_manager: Any = None
        self.mfa_manager: Any = None
        self._authorization_service: Any = None
        self._service: AuthenticationService | None = None
        self._hasher: PasswordHasherProtocol | None = None

    @property
    def password_hasher(self) -> PasswordHasherProtocol:
        """Composed Argon2id-default hasher with a bcrypt legacy shim.

        Builds the single composed instance (ODD-1 Option A): new hashes use
        Argon2id with OWASP-2024 parameters; stored bcrypt hashes keep
        verifying through the legacy shim and upgrade on the next login.
        """
        if self._hasher is None:
            primary = Argon2idPasswordHasher(
                kdf=Argon2idKeyDerivation(
                    config=self._config.password if self._config else None,
                ),
            )
            self._hasher = ComposedPasswordHasher(
                primary=primary,
                legacy=PasswordHasher(),
            )
        return self._hasher

    @property
    def service(self) -> AuthenticationService:
        """Get or create the authentication service."""
        if self._service is None:
            self._service = AuthenticationService(
                password_policy=self.password_policy,
                user_store=self.user_store,
                token_manager=self.token_manager,
                password_hasher=self.password_hasher,
            )
        return self._service

    async def get_user(self, user_id: str) -> Any | None:
        """Fetch a user by their ID.

        Satisfies :class:`~quadkit.contracts.auth.AuthProviderProtocol`.

        Args:
            user_id: The unique identifier of the user to retrieve.

        Returns:
            The user object, or ``None`` if not found.
        """
        return await self.user_store.get_user_by_id(user_id)

    def has_any_role(self, user: Any, roles: list[str]) -> bool:
        """Return True if *user* holds at least one of the given roles.

        Satisfies :class:`~quadkit.contracts.auth.AuthProviderProtocol`.
        Delegates to the sibling :class:`~quadkit.auth.authz.service.AuthorizationService`
        resolved during :meth:`boot`. When no authorization provider is
        registered in the same container (e.g. an app only wires
        ``AuthenticationProvider`` without ``AuthorizationProvider``),
        conservatively returns ``False`` rather than raising.

        Args:
            user: Authenticated user object.
            roles: Role names to check.

        Returns:
            True if the user has at least one of the supplied roles.
        """
        if self._authorization_service is None:
            return False
        return bool(self._authorization_service.has_any_role(user, roles))

    def has_any_permission(self, user: Any, permissions: list[str]) -> bool:
        """Return True if *user* has at least one of the given permissions.

        Satisfies :class:`~quadkit.contracts.auth.AuthProviderProtocol`.
        See :meth:`has_any_role` for delegation and fallback behavior.

        Args:
            user: Authenticated user object.
            permissions: Permission names to check.

        Returns:
            True if the user has at least one of the supplied permissions.
        """
        if self._authorization_service is None:
            return False
        return bool(self._authorization_service.has_any_permission(user, permissions))

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        """Register authentication services with the container.

        Registers the protocols for dependency injection across extensions
        without direct imports.  The single ``PasswordHasherProtocol``
        binding is the composed hasher (Argon2id default, bcrypt legacy
        shim) — one registration per protocol per AGENTS.md §2.6.
        """
        # Register concrete implementations
        container.singleton(PasswordPolicy, lambda: self.password_policy)
        container.singleton(UserStoreProtocol, lambda: self.user_store)
        container.singleton(AuthenticationService, lambda: self.service)

        # Register protocol mappings for cross-extension compatibility (CROSS-EXT-02)
        # This allows other extensions to depend on protocols rather than concrete classes
        container.singleton(PasswordHasherProtocol, self.password_hasher)
        container.singleton(PasswordPolicyProtocol, lambda: self.password_policy)
        from quadkit.contracts.auth import AuthenticatorProtocol, AuthProviderProtocol

        # Only register self as AuthProviderProtocol when no other provider
        # has already claimed this slot (e.g., an application-level AuthService).
        if not container.has(AuthProviderProtocol):
            container.singleton(AuthProviderProtocol, lambda: self)

        # Bind AuthenticatorProtocol to a real implementation. AuthModule.configure()
        # declares this in its exports=[...] list, but until this binding existed
        # nothing ever registered a container key for it — every *Authenticator
        # class (JwtAuthenticator/ApiKeyAuthenticator/SessionAuthenticator) only
        # handles one credential scheme and was wired solely as a private
        # AuthMiddleware attribute, never as a standalone service. Bind the
        # composite (tries API key, then session, then JWT) so the export is
        # honest and resolvable.
        if not container.has(AuthenticatorProtocol):
            from quadkit.auth.web.middleware.composite_authenticator import (
                CompositeRequestAuthenticator,
            )

            # AuthenticationProvider satisfies AuthProviderProtocol structurally
            # (verified at runtime — see composite_authenticator's constructor
            # contract) but mypy's structural check for this Protocol requires
            # an explicit cast here because several optional protocol attributes
            # (session_manager, api_key_manager, mfa_manager) are absent on this
            # class and only ever set on richer AuthProviderProtocol
            # implementations; at runtime CompositeRequestAuthenticator only
            # ever accesses them via getattr-safe checks in its sub-authenticators.
            auth_provider = cast("AuthProviderProtocol", self)
            container.singleton(
                AuthenticatorProtocol,
                factory=lambda: CompositeRequestAuthenticator(auth_provider),
            )

    async def boot(self, container: BootContainerProtocol) -> None:
        """Initialize authentication provider and register with kernel health registry."""
        logger.info("AuthenticationProvider started")
        hooks = await container.resolve_optional(HookRegistryProtocol)
        self.service.set_hook_registry(hooks)
        if self.token_manager is not None and hasattr(
            self.token_manager, "set_hook_registry"
        ):
            self.token_manager.set_hook_registry(hooks)

        # Token revocation needs a cache backend; when none was supplied at
        # construction, adopt the application default cache so
        # ``logout_all_user_tokens`` works without extra wiring.
        if self.token_manager is not None and hasattr(
            self.token_manager, "set_blacklist_resolver"
        ):
            # Ordering-proof: auth boots before cache providers, so hand a
            # deferred source over the root resolver instead of resolving now.
            self.token_manager.set_blacklist_resolver(
                lambda: _resolve_default_cache_sync(container)
            )

        if container is not None and hasattr(container, "resolve"):
            with contextlib.suppress(
                ImportError, AttributeError, RuntimeError, TypeError
            ):
                from quadkit.contracts.observability.metrics import (
                    HealthCheckRegistryProtocol,
                )

                registry = await container.resolve_optional(HealthCheckRegistryProtocol)
                if registry is not None:
                    registry.add("authentication", self.health_check)

        await self._attach_sibling_managers(container)

    async def _attach_sibling_managers(self, container: BootContainerProtocol) -> None:
        """Attach sibling-provider managers so this satisfies ``AuthProviderProtocol``.

        ``register()`` runs for every provider in the application before any
        ``boot()`` runs (see ``LifecycleManager.boot_all``), so by the time
        this method executes, any co-registered ``SessionProvider``,
        ``AuthorizationProvider``, or ``MFAProvider`` have already bound
        their services into the container — regardless of relative boot
        order within the same priority level. Each lookup is optional: an
        application that only wires ``AuthenticationProvider`` (no sessions,
        no RBAC, no MFA) keeps these as ``None``, exactly as
        ``AuthProviderProtocol`` documents ("None when the feature is
        disabled/not configured").
        """
        if container is None or not hasattr(container, "resolve_optional"):
            return

        with contextlib.suppress(
            ImportError, AttributeError, RuntimeError, TypeError, LookupError
        ):
            from quadkit.auth.session.manager import SessionManagerImpl

            self.session_manager = await container.resolve_optional(SessionManagerImpl)

        with contextlib.suppress(
            ImportError, AttributeError, RuntimeError, TypeError, LookupError
        ):
            from quadkit.auth.authz.service import AuthorizationService

            self._authorization_service = await container.resolve_optional(
                AuthorizationService
            )

        with contextlib.suppress(
            ImportError, AttributeError, RuntimeError, TypeError, LookupError
        ):
            from quadkit.auth.mfa.manager import MFAManager

            self.mfa_manager = await container.resolve_optional(MFAManager)

        with contextlib.suppress(
            ImportError, AttributeError, RuntimeError, TypeError, LookupError
        ):
            from quadkit.auth.authn.apikeys import APIKeyManager

            self.api_key_manager = await container.resolve_optional(APIKeyManager)

    async def shutdown(self) -> None:
        """Shutdown authentication provider."""
        logger.info("AuthenticationProvider shutdown")

    async def verify_token(self, token: str) -> Result[VerifiedToken, TokenError]:
        """Verify a JWT token and return a ``Result`` with the decoded payload.

        Satisfies :class:`~quadkit.contracts.auth.AuthProviderProtocol`.

        Delegates to ``token_manager.verify_token()`` when a token manager
        is configured.  Returns an ``Err`` result if no token manager is set
        or if the token is invalid for any expected domain reason.

        Infrastructure failures (cache unavailable, network errors) are still
        raised as exceptions and must be handled by the caller.

        Args:
            token: The JWT token string to verify.

        Returns:
            ``Ok(VerifiedToken)`` if the token is valid and not revoked,
            or ``Err(TokenError)`` for expected domain failures.
        """
        from quadkit.auth.exceptions import TokenInvalidError

        if self.token_manager is None:
            return Err(TokenInvalidError("Authentication not configured"))  # type: ignore[arg-type]
        return cast(
            "Result[VerifiedToken, TokenError]",
            await self.token_manager.verify_token(token),
        )

    async def validate_session(self, token: str) -> Any:
        """Validate a session token and return user information.

        Delegates to the underlying authentication service's
        ``get_user_from_token`` method.  Returns a
        ``Result[VerifiedToken, TokenError]`` or ``None`` when no token
        manager is configured.

        Args:
            token: The session or JWT token to validate.

        Returns:
            ``Result[VerifiedToken, TokenError]`` on success/failure, or ``None``.
        """
        if self.token_manager is None:
            return None
        return await self.service.get_user_from_token(token)

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Check authentication provider health."""
        return HealthCheckResult(
            component=self.name,
            status=HealthStatus.HEALTHY,
            details={
                "service": "authentication",
                "password_policy": str(self.password_policy),
                "user_store_type": type(self.user_store).__name__,
            },
        )
