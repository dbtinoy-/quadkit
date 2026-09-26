"""Token verification seam for :class:`~quadkit.auth.authn.jwt.JWTTokenManager`.

This module is an internal implementation detail; import
:class:`~quadkit.auth.authn.jwt.JWTTokenManager` directly.
"""

from __future__ import annotations

from collections import OrderedDict
import hashlib
from typing import TYPE_CHECKING, Any

import jwt
from jwt.types import Options

from quadkit.auth.authn._binding import TokenBindingConfig, verify_binding
from quadkit.contracts.auth.exceptions import TokenError as ContractsTokenError

if TYPE_CHECKING:
    from quadkit.contracts.auth.token import VerifiedToken
    from quadkit.contracts.core import HookRegistryProtocol
    from quadkit.logging import LoggerProtocol as Logger
    from quadkit.result import Result


class _JWTVerificationMixin:
    """Mixin providing JWT token verification for :class:`JWTTokenManager`.

    All public attributes referenced here are initialised by
    ``JWTTokenManager.__init__``; they are declared below as class-level
    annotations solely to satisfy static type checkers.
    """

    # ── Attributes set by JWTTokenManager.__init__ ───────────────────────────
    algorithm: str
    _required_audience: str | None
    _binding_config: TokenBindingConfig | None
    _verification_cache: OrderedDict[str, str]
    _verified_by_key: dict[str, str]
    logger: Logger
    _hooks: HookRegistryProtocol | None

    @property
    def keys(self) -> dict[str, Any]:  # pragma: no cover
        """Live key material — provided by JWTTokenManager."""
        raise NotImplementedError

    @property
    def current_key_id(self) -> str:  # pragma: no cover
        """Active signing key ID — provided by JWTTokenManager."""
        raise NotImplementedError

    def _get_verification_key(self, kid: str) -> str:  # pragma: no cover
        """Return raw verification key — provided by JWTTokenManager."""
        raise NotImplementedError

    async def _is_token_blacklisted(self, token: str) -> bool:  # pragma: no cover
        """Blacklist lookup — provided by ``_JWTRevocationMixin``."""
        raise NotImplementedError

    async def _emit_action(self, hook_name: str, payload: object) -> None:
        """Emit a token lifecycle hook when a registry is available."""
        if self._hooks is None:
            return

        await self._hooks.call_action(hook_name, payload=payload)

    async def verify_token(
        self,
        token: str,
        token_type: str = "access",  # noqa: S107  # not a password; identifies token kind
        expected_audience: str | None = None,
        required_scope: str | None = None,
        binding_context: dict[str, str] | None = None,
        *,
        allow_missing_audience: bool = False,
    ) -> Result[VerifiedToken, ContractsTokenError]:
        """Verify and decode a JWT token with support for multiple keys.

        Returns a ``Result`` rather than raising domain exceptions.  Only
        infrastructure failures (cache down, network errors) are still raised
        as exceptions so the event loop can propagate them properly.

        Args:
            token: The JWT token to verify.
            token_type: Expected token type ("access" or "refresh").
            expected_audience: Expected audience claim ("aud") for validation.
                Takes precedence over ``required_audience`` set on the manager.
            required_scope: Required scope claim for validation.
            binding_context: Optional request context dict for token binding.
            allow_missing_audience: When ``True``, audience validation is skipped
                entirely regardless of ``required_audience`` on the manager.
                Use only for trusted internal service paths that explicitly opt
                out of audience enforcement.

        Returns:
            ``Ok(VerifiedToken)`` if the token is valid and not revoked.
            ``Err(TokenError)`` for expected domain failures (expired,
            blacklisted, invalid signature, wrong type, audience mismatch, etc.).

        Raises:
            RuntimeError: If the cache backend is unavailable (infrastructure).
            OSError: On network-level failures (infrastructure).
            ConnectionError: On connection failures (infrastructure).
        """
        from quadkit.auth.exceptions import TokenAudienceError, TokenInvalidError
        from quadkit.auth.exceptions import (
            TokenBlacklistedError as ContractsBlacklistedError,
        )
        from quadkit.auth.exceptions import (
            TokenExpiredError as ContractsExpiredError,
        )
        from quadkit.contracts.auth.token import VerifiedToken
        from quadkit.result import Err, Ok

        try:
            # Compute a short token hash for the verification cache.
            # 16 hex chars (64 bits) is sufficient for an in-process lookup;
            # the full token is never stored.
            token_hash = hashlib.sha256(token.encode()).hexdigest()

            # Get key ID from header
            header = jwt.get_unverified_header(token)
            kid = header.get("kid", self.current_key_id)

            # Check if key exists
            if kid not in self.keys:
                return Err(TokenInvalidError("Unknown signing key ID"))  # type: ignore[arg-type]

            # Fast path: if we have already verified this exact token recently,
            # skip the kid-based lookup and go straight to the cached key_id.
            # Fall back to the per-kid cache, then the kid header itself.
            cached_key_id = self._verification_cache.get(token_hash)
            if cached_key_id and cached_key_id in self.keys:
                effective_key_id = cached_key_id
                self._verification_cache.move_to_end(
                    token_hash
                )  # mark as recently used
            else:
                # Try the key that last successfully verified this kid (fast path),
                # fall back to kid itself if the cached entry is absent or stale.
                effective_key_id = self._verified_by_key.get(kid, kid)
                if effective_key_id not in self.keys:
                    effective_key_id = kid

            # Verify with correct key
            verification_key = self._get_verification_key(effective_key_id)

            # Resolve the effective audience for this call:
            #   1. An explicit call-site audience always wins.
            #   2. Fall back to the manager-level required_audience.
            #   3. When allow_missing_audience=True, skip the check entirely.
            if allow_missing_audience:
                effective_audience: str | None = None
                decode_options: Options = Options({"verify_aud": False})
            else:
                effective_audience = expected_audience or self._required_audience
                decode_options = Options({"verify_aud": effective_audience is not None})
                if effective_audience is None:
                    import os

                    if os.getenv("QK_ENV", "development") == "production":
                        self.logger.warning(
                            "jwt_verification_without_audience",
                            token_type=token_type,
                        )

            payload = jwt.decode(
                token,
                verification_key,
                algorithms=[self.algorithm],
                audience=effective_audience,
                options=decode_options,
            )

            # Record which key_id successfully verified this kid and this token.
            self._verified_by_key[kid] = effective_key_id
            if len(self._verification_cache) >= 1000:
                self._verification_cache.popitem(last=False)  # evict LRU (oldest)
            self._verification_cache[token_hash] = effective_key_id

            # Check token type — only enforce if the payload explicitly declares one.
            # External JWTs (e.g. NextAuth HS256 tokens) omit the "type" claim; rejecting
            # them here would silently break all external-JWT auth flows.
            declared_type = payload.get("type")
            if declared_type is not None and declared_type != token_type:
                return Err(
                    TokenInvalidError(f"Invalid token type: expected {token_type}")  # type: ignore[arg-type]
                )

            # Validate audience explicitly if jwt.decode didn't handle it fully
            if effective_audience:
                token_aud = payload.get("aud")
                if isinstance(token_aud, list):
                    if effective_audience not in token_aud:
                        return Err(
                            TokenAudienceError(  # type: ignore[arg-type]
                                f"Invalid audience: {effective_audience}"
                            )
                        )
                elif token_aud != effective_audience:
                    return Err(
                        TokenAudienceError(f"Invalid audience: {effective_audience}")  # type: ignore[arg-type]
                    )

            # Validate scope if required
            if required_scope:
                token_scope = payload.get("scope", "")
                if required_scope not in token_scope.split():
                    return Err(
                        TokenInvalidError(f"Required scope missing: {required_scope}")  # type: ignore[arg-type]
                    )

            # Verify client binding if configured
            if self._binding_config and binding_context is not None:
                if not verify_binding(self._binding_config, payload, binding_context):
                    return Err(TokenInvalidError("Token binding mismatch"))  # type: ignore[arg-type]

            # Check if token is blacklisted — may raise RuntimeError (infra)
            if await self._is_token_blacklisted(token):
                return Err(ContractsBlacklistedError("Token has been revoked"))  # type: ignore[arg-type]

            from datetime import UTC

            # Surface application-defined claims; registered + known claims
            # are already mapped to typed fields above.
            _known = {
                "sub",
                "email",
                "name",
                "roles",
                "permissions",
                "exp",
                "iat",
                "nbf",
                "iss",
                "jti",
                "aud",
                "type",
                "scope",
            }
            extra_claims = {
                key: value
                for key, value in payload.items()
                if key not in _known and not key.startswith("_")
            }

            return Ok(
                VerifiedToken(
                    user_id=payload.get("sub", ""),
                    email=payload.get("email", ""),
                    name=payload.get("name", ""),
                    roles=payload.get("roles", []),
                    permissions=payload.get("permissions", []),
                    expires_at=__import__("datetime").datetime.fromtimestamp(
                        payload.get("exp", 0), tz=UTC
                    ),
                    key_id=kid,
                    token_type=token_type,
                    audience=effective_audience,
                    extra_claims=extra_claims,
                )
            )

        except jwt.ExpiredSignatureError:
            return Err(ContractsExpiredError("Token has expired"))  # type: ignore[arg-type]
        except jwt.InvalidAudienceError:
            return Err(TokenAudienceError("Invalid audience"))  # type: ignore[arg-type]
        except (jwt.InvalidTokenError, ValueError) as e:
            return Err(TokenInvalidError(f"Invalid token: {e}"))  # type: ignore[arg-type]
        except (RuntimeError, OSError, ConnectionError):
            # Documented infrastructure propagation (cache down, network
            # errors) — raised so the event loop can propagate them.
            raise
        except Exception as e:  # noqa: BLE001 — any other failure (e.g. JWKS fetch) is a domain Err, never a raw raise
            return Err(ContractsTokenError(f"Token verification failed: {e}"))
