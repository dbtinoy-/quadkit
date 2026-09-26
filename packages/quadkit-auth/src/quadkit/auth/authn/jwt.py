"""JWT token management for authentication.

Provides :class:`JWTTokenManager` for JWT creation, validation, and refresh.
Key lifecycle is delegated to :mod:`key_rotation` (:class:`JWTKeyStore`) and
persistent revocation to :mod:`revocation` (:class:`PersistentTokenRevocationStore`).

Example::

    manager = JWTTokenManager(
        current_key_id="key-1",
        keys={"key-1": SecretStr("secret-key-at-least-32-chars")},
    )
    token = await manager.create_access_token(user_id="123")
    result = await manager.verify_token(token)
"""

from __future__ import annotations

from collections import OrderedDict
import os
from typing import TYPE_CHECKING, Any

from quadkit.auth import constants as const
from quadkit.auth.authn._binding import TokenBindingConfig
from quadkit.auth.authn._jwt_creation import _JWTCreationMixin
from quadkit.auth.authn._jwt_lifecycle import _JWTLifecycleMixin
from quadkit.auth.authn._key_utils import normalize_jwt_keys
from quadkit.auth.authn.blacklist import JWTBlacklist
from quadkit.auth.authn.key_rotation import JWTKeyStore
from quadkit.contracts.exceptions import ConfigurationError
from quadkit.logging import LoggerProtocol as Logger
from quadkit.logging import get_logger
from quadkit.validation import SecretStr

_logger = get_logger(__name__)

if TYPE_CHECKING:
    from quadkit.contracts.audit import AuditLoggerProtocol
    from quadkit.contracts.auth.exceptions import TokenError as ContractsTokenError
    from quadkit.contracts.auth.token import VerifiedToken
    from quadkit.contracts.core import HookRegistryProtocol
    from quadkit.contracts.core.identity import IdGeneratorProtocol
    from quadkit.contracts.infra.cache import CacheBackendProtocol
    from quadkit.result import Result


class JWTTokenManager(_JWTCreationMixin, _JWTLifecycleMixin):
    """JWT token management with key rotation support.

    The JWTTokenManager handles creation, validation, and renewal of JWT
    tokens for user authentication. It supports multiple signing keys
    for seamless key rotation without invalidating existing tokens.

    Attributes:
        current_key_id: ID of the currently active signing key.
        keys: Dictionary of key_id -> key material.
        algorithm: JWT signing algorithm (HS256, RS256, etc.).
        access_expiration_hours: Expiration time for access tokens.
        refresh_expiration_days: Expiration time for refresh tokens.
        cache_service: Optional cache backend for token validation caching.
        rotation_interval: Interval in seconds between key rotations.

    Example:
        Basic token operations::

            manager = JWTTokenManager(
                current_key_id="v1",
                keys={"v1": SecretStr("secure-secret-key")},
            )

            # Create access token
            token = await manager.create_access_token(user_id="user123")

            # Verify and decode
            payload = await manager.verify_token(token)

    Note:
        In production, secrets should not be hardcoded. Use environment
        variables or a secrets management service.
    """

    def __init__(
        self,
        current_key_id: str,
        keys: dict[str, str | SecretStr | dict[str, str | SecretStr]] | None = None,
        algorithm: str = const.DEFAULT_TOKEN_ALGORITHM,
        access_expiration_hours: int = 24,
        refresh_expiration_days: int = 30,
        cache_service: CacheBackendProtocol | None = None,
        rotation_interval_days: int = 90,
        grace_period_seconds: int = const.DEFAULT_JWT_KEY_ROTATION_GRACE_PERIOD_SECONDS,
        logger: Logger | None = None,
        *,
        audit_logger: AuditLoggerProtocol | None = None,
        binding_config: TokenBindingConfig | None = None,
        required_audience: str | None = None,
        ids: IdGeneratorProtocol | None = None,
    ) -> None:
        """Initialize the JWT token manager.

        Args:
            current_key_id: The ID of the currently active signing key.
            keys: Dictionary mapping key IDs to key material. If None,
                current_key_id is treated as a single secret.
            algorithm: JWT signing algorithm (e.g., "HS256", "RS256").
            access_expiration_hours: Hours until access tokens expire.
            refresh_expiration_days: Days until refresh tokens expire.
            cache_service: Optional cache backend for token validation.
            rotation_interval_days: Days between key rotations.
            grace_period_seconds: Seconds after key rotation during which tokens
                signed by the outgoing key remain valid. Defaults to 3600 (1 hour).
                Set to 0 to invalidate all old-key tokens immediately on rotation.
            audit_logger: Optional :class:`~quadkit.contracts.audit.AuditLoggerProtocol`
                used to record token revocation events.  When not provided,
                no audit entries are written.
            binding_config: Optional :class:`TokenBindingConfig` for opt-in client
                binding.  When set, tokens embed a ``bind`` claim containing a
                SHA-256 hash of active binding factors (IP, fingerprint).  Tokens
                issued without a ``bind`` claim continue to verify successfully so
                that binding can be enabled incrementally.
            required_audience: When set, every call to ``verify_token`` will
                enforce that the token's ``aud`` claim matches this value.
                Pass ``allow_missing_audience=True`` to ``verify_token`` to
                bypass the check on a per-call basis for trusted internal paths.
        """
        if keys is None:
            # Single secret mode for backward compatibility and simple usage
            raw = current_key_id
            _resolved_key_id = "default"
            _resolved_keys = normalize_jwt_keys({"default": raw})
        else:
            if not keys:
                raise ValueError("keys cannot be empty")
            _resolved_key_id = current_key_id
            _resolved_keys = normalize_jwt_keys(keys)

        # Ensure the current key exists in the keys dictionary
        if _resolved_key_id not in _resolved_keys:
            raise ValueError(
                f"current_key_id '{_resolved_key_id}' not found in keys",
            )

        # Defensive GuardProtocol: Ensure secret is not a known weak default in production
        env = os.getenv("QK_ENV", "development").lower()
        if env in ("production", "staging"):
            weak_secrets = ["change-me-in-production", "secret", "password", "123456"]
            for key_val in _resolved_keys.values():
                if isinstance(key_val, dict):
                    # Asymmetric keys — skip weak-key check (PEM keys are always long)
                    continue
                secret_str = key_val.get_secret_value()
                if any(w in secret_str.lower() for w in weak_secrets) or (
                    len(secret_str) < 32
                ):
                    raise ConfigurationError(
                        "Insecure JWT secret key detected in production environment",
                    )

        # Reject unsigned ("none") and unknown algorithms. This value is passed
        # straight into PyJWT's `algorithms` allow-list in verify_token, so
        # "none" would accept tokens with no signature at all, and typos
        # (e.g. "HS512 ") would fail opaquely at decode time.
        import jwt as _pyjwt

        if algorithm.lower() == "none":
            raise ConfigurationError(
                "JWT algorithm 'none' (unsigned tokens) is not allowed",
            )
        if algorithm not in _pyjwt.algorithms.get_default_algorithms():
            raise ConfigurationError(
                f"Unsupported JWT algorithm: {algorithm!r}",
            )

        # Delegate all key lifecycle management to JWTKeyStore
        self._key_store = JWTKeyStore(
            current_key_id=_resolved_key_id,
            keys=_resolved_keys,
            grace_period_seconds=float(grace_period_seconds),
        )

        # Initialize mixin with ID generator
        super().__init__(ids=ids)

        self.algorithm = algorithm
        self.access_expiration_hours = access_expiration_hours
        self.refresh_expiration_days = refresh_expiration_days
        self.cache_service = cache_service
        self.rotation_interval = rotation_interval_days * 86400  # Convert to seconds
        self.grace_period_seconds = grace_period_seconds

        if logger is None:
            from quadkit.logging import get_logger

            logger = get_logger(__name__)
        self.logger = logger.bind(manager="JWTTokenManager")

        self._audit_logger: AuditLoggerProtocol | None = audit_logger
        self._binding_config = binding_config
        self._required_audience: str | None = required_audience
        self._hooks: HookRegistryProtocol | None = None

        # Blacklist — delegates to JWTBlacklist which handles both in-process
        # and cache-backed revocation.
        self._blacklist_mgr = JWTBlacklist(
            cache=cache_service,
            cache_resolver=getattr(self, "_blacklist_cache_resolver", None),
            algorithm=algorithm,
            current_key_id_fn=lambda: self._key_store.current_key_id,
            access_expiration_hours=access_expiration_hours,
            refresh_expiration_days=refresh_expiration_days,
            audit_logger=audit_logger,
        )

        # Per-kid key cache: maps the JWT ``kid`` header claim to the key_id
        # that most recently verified a token carrying that kid.  On the next
        # verification for the same kid the cached key_id is tried first,
        # avoiding redundant lookups when many rotation keys are present.
        # Cleared on every call to :meth:`rotate_key`.
        self._verified_by_key: dict[str, str] = {}

        # Verification result cache: maps a short token hash (first 16 hex
        # chars of SHA-256) to the key_id that last successfully verified it.
        # Allows skipping the kid-based lookup entirely on repeated calls for
        # the same token — common in middleware that re-validates per request.
        # Bounded at 1 000 entries; cleared in full when the limit is hit to
        # avoid unbounded memory growth.  Also cleared on key rotation.
        self._verification_cache: OrderedDict[str, str] = OrderedDict()

        # ── Key-store properties ─────────────────────────────────────────────

    @property
    def keys(self) -> dict[str, Any]:
        """Live view of the key material managed by the key store."""
        return self._key_store.keys

    @property
    def _key_meta(self) -> dict[str, Any]:
        """Live view of the key metadata managed by the key store."""
        return self._key_store._key_meta

    @property
    def current_key_id(self) -> str:
        """The key ID currently used for signing new tokens."""
        return self._key_store.current_key_id

    @current_key_id.setter
    def current_key_id(self, value: str) -> None:
        """Allow external callers to update the active key ID on the store."""
        self._key_store.current_key_id = value

    def set_blacklist_resolver(self, resolver: Any) -> None:
        """Attach a deferred blacklist-cache source.

        Args:
            resolver: Zero-arg callable returning a ``CacheBackendProtocol``
                or ``None``; invoked lazily on first revocation use.
        """
        self._blacklist_cache_resolver = resolver
        self._blacklist_mgr.attach_cache_resolver(resolver)

    def set_blacklist_cache(self, cache: Any) -> None:
        """Attach a cache backend to the blacklist for durable revocation.

        Lets DI providers supply the application cache during ``boot()``
        when it was not available at construction time.

        Args:
            cache: Cache backend used for token/user revocation entries.
        """
        self._blacklist_mgr.attach_cache(cache)

    def __repr__(self) -> str:
        """Return developer-friendly string representation."""
        return (
            f"JWTTokenManager(algorithm={self.algorithm!r}, "
            f"access_expiration_hours={self.access_expiration_hours}, "
            f"current_key_id={self.current_key_id!r})"
        )

    def set_hook_registry(self, hooks: HookRegistryProtocol | None) -> None:
        """Attach an optional hook registry after provider boot wiring."""
        self._hooks = hooks

    async def rotate_key(self, new_key_id: str, new_secret: str | dict) -> None:
        """Rotate to a new signing key, delegating lifecycle to the key store.

        Old keys are retained for ``grace_period_seconds`` (constructor
        parameter, default 3600 s) so tokens they signed remain verifiable
        during the overlap window.

        Args:
            new_key_id: ID for new key.
            new_secret: New secret key (string for symmetric or dict for asymmetric).
        """
        await self._key_store.rotate(new_key_id, new_secret)
        # Clear the per-kid and per-token verification caches so stale mappings
        # are not used after rotation (new keys may have the same kid value).
        self._verified_by_key.clear()
        self._verification_cache.clear()

    async def _cleanup_old_keys(self) -> None:
        """Delegate old-key cleanup to the key store."""
        await self._key_store._cleanup_old_keys()

    def list_keys(self) -> dict[str, dict[str, Any]]:
        """Return current key metadata (for inspection/operations)."""
        return self._key_store.list_keys()

    def _get_signing_key(self) -> str:
        """Return the raw signing key string for the current key ID."""
        return self._key_store.get_signing_key()

    def _get_verification_key(self, kid: str) -> str:
        """Return the raw verification key string for *kid*."""
        return self._key_store.get_verification_key(kid)  # type: ignore[return-value]

    async def get_user_from_token(
        self, token: str
    ) -> Result[VerifiedToken, ContractsTokenError]:
        """Extract user information from access token.

        Returns:
            ``Ok(VerifiedToken)`` if the token is a valid access token, or
            ``Err(TokenError)`` for expected domain failures.
        """
        return await self.verify_token(token, "access")


__all__ = ["JWTTokenManager", "TokenBindingConfig"]
