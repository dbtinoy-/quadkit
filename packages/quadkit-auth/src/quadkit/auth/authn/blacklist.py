"""JWT token blacklist management.

Provides :class:`JWTBlacklist` for revoking individual tokens and all tokens
for a user. Supports both in-process (fallback) and cache-backed storage.

Key schema:
- Individual token: ``jwt:blacklist:{sha256_hex}``
- User-level block:  ``jwt:blacklist:user:{user_id}``
"""

from __future__ import annotations

import hashlib
import inspect
from typing import TYPE_CHECKING, Any

import jwt

from quadkit.logging import get_logger
from quadkit.primitives import clock as ambient_clock

if TYPE_CHECKING:
    from quadkit.contracts.audit import AuditLoggerProtocol
    from quadkit.contracts.auth.exceptions import TokenError as ContractsTokenError
    from quadkit.contracts.infra.cache import CacheBackendProtocol
    from quadkit.result import Result

__all__ = ["JWTBlacklist"]

logger = get_logger(__name__)


class JWTBlacklist:
    """Hash-based JWT blacklist supporting both cache and in-process storage.

    When a :class:`~quadkit.contracts.cache.CacheBackendProtocol` is provided,
    revocation entries are persisted with a TTL derived from the token's own
    expiry time.  Without a cache the in-process ``_blacklist`` set is used as
    a fallback (entries are lost on process restart).

    Args:
        cache: Optional cache backend for distributed blacklist storage.
        algorithm: JWT signing algorithm string (used in audit entries).
        current_key_id: Callable that returns the active signing key ID.
        access_expiration_hours: Access token lifetime in hours.
        refresh_expiration_days: Refresh token lifetime in days.
        audit_logger: Optional audit logger for revocation events.
    """

    def __init__(
        self,
        cache: CacheBackendProtocol | None,
        algorithm: str,
        current_key_id_fn: Any,
        access_expiration_hours: int,
        refresh_expiration_days: int,
        audit_logger: AuditLoggerProtocol | None = None,
        cache_resolver: Any = None,
    ) -> None:
        self._cache = cache
        self._algorithm = algorithm
        self._current_key_id_fn = current_key_id_fn
        self._access_expiration_hours = access_expiration_hours
        self._refresh_expiration_days = refresh_expiration_days
        self._audit_logger = audit_logger
        self._fallback: set[str] = set()
        self._fallback_users: dict[str, int] = {}
        # Optional late-binding source for the cache when none was supplied
        # at construction (DI ordering: auth boots before cache providers).
        self._cache_resolver: Any = cache_resolver

    def attach_cache(self, cache: Any) -> None:
        """Attach an explicit cache backend immediately."""
        """Attach a cache backend after construction.

        Lets DI providers supply the application cache during ``boot()``
        when it was not available at construction time, enabling
        cache-backed revocation without rebuilding the token manager.

        Args:
            cache: Cache backend implementing the blacklist operations used
                here (``exists``/``set`` semantics of CacheBackendProtocol).
        """
        self._cache = cache

    def attach_cache_resolver(self, resolver: Any) -> None:
        """Attach a deferred cache source invoked on first revocation use.

        Ordering-proof alternative to :meth:`attach_cache`: providers that
        boot before the cache layer can hand over a zero-arg callable
        returning the backend (or ``None``) once it exists.

        Args:
            resolver: Zero-argument callable returning a cache backend or
                ``None``.
        """
        self._cache_resolver = resolver

    async def _effective_cache(self) -> Any:
        """Return the cache backend, resolving lazily when configured.

        Delegates to the attached resolver with
        ``CacheBackendProtocol`` on first use, caching the result.
        """
        if self._cache is not None:
            return self._cache
        if self._cache_resolver is None:
            return None
        try:
            resolved = self._call_resolver()
            if inspect.isawaitable(resolved):
                resolved = await resolved
        except Exception as exc:  # noqa: BLE001 — fail closed below
            logger.warning("blacklist_cache_resolve_failed", error=str(exc))
            return None
        if resolved is None:
            # Not registered yet (DI ordering). Ask again next time rather
            # than pinning ``None`` for the life of the process.
            return None
        self._cache = resolved
        return self._cache

    def _call_resolver(self) -> Any:
        """Invoke the attached resolver with the signature it was given.

        :meth:`attach_cache_resolver` documents a **zero-argument**
        callable; an earlier revision of this method called it with
        ``CacheBackendProtocol`` as a positional argument, so the
        provider-supplied lambda raised ``TypeError`` on every request and
        revocation silently stayed in the per-process fallback set. Both
        shapes are accepted so an application that already passed a
        one-argument resolver keeps working.
        """
        resolver = self._cache_resolver
        try:
            params = inspect.signature(resolver).parameters
        except (TypeError, ValueError):
            return resolver()
        if any(
            p.default is inspect.Parameter.empty
            and p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
            for p in params.values()
        ):
            from quadkit.contracts.infra.cache import CacheBackendProtocol

            return resolver(CacheBackendProtocol)
        return resolver()

    @staticmethod
    def _flag(result: Any) -> bool:
        """Normalise a cache operation to a plain boolean.

        Backends return ``Result[bool, CacheError]``; treating that as a
        bool makes ``Ok(False)`` truthy — historically flagging every token
        as revoked the moment a cache was attached. Unwraps Results,
        mapping ``Err`` to ``False`` (callers fail closed separately).
        """
        if result is None:
            return False
        unwrap = getattr(result, "unwrap", None)
        if callable(unwrap):
            try:
                return bool(result.unwrap())
            except Exception:  # noqa: BLE001 — Err branch
                return False
        return bool(result)

    @staticmethod
    def _written(result: Any) -> bool:
        """Normalise a cache **write** to a plain boolean.

        ``CacheBackendProtocol.set`` returns ``Ok(None)`` on success —
        there is no payload to unwrap — so :meth:`_flag` (which exists for
        ``exists``/``get`` and reads the *inner* value) reported every
        successful write as a failure the moment a real backend was
        attached: the key was set, the token was revoked, and the caller
        still got ``Err("Token revocation failed")``. Found by qk-erp:
        ``POST /logout`` answered 401 for a logout that had worked.
        """
        if result is None:
            return False
        is_ok = getattr(result, "is_ok", None)
        if callable(is_ok):
            return bool(is_ok())
        return bool(result)

    # ── Public API ────────────────────────────────────────────────────────

    async def revoke(self, token: str) -> Result[None, ContractsTokenError]:
        """Add *token* to the blacklist.

        Args:
            token: The raw JWT string to revoke.

        Returns:
            ``Ok(None)`` on success or if the token is already expired.
            ``Err(TokenError)`` if the cache write fails.

        Raises:
            RuntimeError: On cache-level infrastructure failures.
            OSError: On network-level failures.
            ConnectionError: On connection failures.
        """
        from quadkit.contracts.auth.exceptions import TokenError as ContractsTokenError
        from quadkit.result import Err, Ok

        token_hash = hashlib.sha256(token.encode()).hexdigest()
        cache = await self._effective_cache()

        if not cache:
            self._fallback.add(token_hash)
            return Ok(None)

        try:
            unverified_payload = jwt.decode(token, options={"verify_signature": False})
            exp = unverified_payload.get("exp", 0)
            now = int(ambient_clock.timestamp())
            ttl = max(0, exp - now)

            if ttl <= 0:
                return Ok(None)

            blacklist_key = f"jwt:blacklist:{token_hash}"
            success = self._written(
                await cache.set(key=blacklist_key, value="1", ttl=ttl)
            )

            if success and self._audit_logger is not None:
                from quadkit.contracts.audit import AuditEntry

                actor_id = str(unverified_payload.get("sub", "unknown"))
                await self._audit_logger.log(
                    AuditEntry(
                        action="token.revoked",
                        actor_id=actor_id,
                        resource_type="Token",
                        resource_id=token_hash[:16],
                        outcome="success",
                        metadata={
                            "algorithm": self._algorithm,
                            "key_id": self._current_key_id_fn(),
                        },
                    )
                )

            return (
                Ok(None)
                if success
                else Err(ContractsTokenError("Token revocation failed"))
            )

        except Exception:  # noqa: BLE001 — log any revocation failure, then re-raise
            logger.exception("token_revoke_failed")
            raise

    async def revoke_all_for_user(
        self, user_id: str
    ) -> Result[None, ContractsTokenError]:
        """Blacklist all tokens for *user_id* by writing a user-level sentinel.

        Args:
            user_id: The subject (``sub``) claim of the tokens to revoke.

        Returns:
            ``Ok(None)`` on success. ``Err(TokenError)`` if the write fails.

        Without a cache backend, writes an in-process user-level sentinel
        that lasts for the maximum configured token lifetime.
        """
        from quadkit.contracts.auth.exceptions import TokenError as ContractsTokenError
        from quadkit.result import Err, Ok

        cache = await self._effective_cache()
        max_token_ttl = max(
            self._access_expiration_hours * 3600,
            self._refresh_expiration_days * 86400,
        )
        if not cache:
            self._fallback_users[str(user_id)] = (
                int(ambient_clock.timestamp()) + max_token_ttl
            )
            return Ok(None)

        try:
            blacklist_key = f"jwt:blacklist:user:{user_id}"
            success = self._written(
                await cache.set(
                    key=blacklist_key,
                    value=int(ambient_clock.timestamp()),
                    ttl=max_token_ttl,
                )
            )
            return (
                Ok(None)
                if success
                else Err(ContractsTokenError("Failed to revoke all user tokens"))
            )
        except Exception:  # noqa: BLE001 — log any revocation failure, then re-raise
            logger.exception("token_revoke_all_failed", user_id=user_id)
            raise

    async def is_blacklisted(self, token: str) -> bool:
        """Return ``True`` if *token* has been revoked.

        Checks both the individual token hash and the user-level sentinel.
        Fails closed on cache errors (returns ``True``).

        Args:
            token: The raw JWT string to check.

        Returns:
            ``True`` if the token should be rejected, ``False`` otherwise.
        """
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        cache = await self._effective_cache()

        if not cache:
            if token_hash in self._fallback:
                return True
            try:
                unverified_payload = jwt.decode(
                    token, options={"verify_signature": False}
                )
            except Exception:  # noqa: BLE001 - invalid tokens are rejected by verification proper
                return False
            user_id = unverified_payload.get("sub")
            if not user_id:
                return False
            expires_at = self._fallback_users.get(str(user_id))
            if expires_at is None:
                return False
            if expires_at <= int(ambient_clock.timestamp()):
                self._fallback_users.pop(str(user_id), None)
                return False
            return True

        try:
            if self._flag(await cache.exists(f"jwt:blacklist:{token_hash}")):
                return True

            unverified_payload = jwt.decode(token, options={"verify_signature": False})
            user_id = unverified_payload.get("sub")
            return bool(
                user_id
                and self._flag(await cache.exists(f"jwt:blacklist:user:{user_id}"))
            )

        except Exception:  # noqa: BLE001 — fail closed: any blacklist-check failure means "treat as revoked"
            logger.exception("token_blacklist_check_failed")
            return True  # Fail closed
