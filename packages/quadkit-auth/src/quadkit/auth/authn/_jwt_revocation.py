"""Revocation / blacklist seam for :class:`~quadkit.auth.authn.jwt.JWTTokenManager`.

This module is an internal implementation detail; import
:class:`~quadkit.auth.authn.jwt.JWTTokenManager` directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import jwt

from quadkit.auth.authn._jwt_verification import _JWTVerificationMixin
from quadkit.auth.authn.blacklist import JWTBlacklist
from quadkit.contracts.auth.exceptions import TokenError as ContractsTokenError

if TYPE_CHECKING:
    from quadkit.logging import LoggerProtocol as Logger
    from quadkit.result import Result


class _JWTRevocationMixin(_JWTVerificationMixin):
    """Mixin providing token revocation for :class:`JWTTokenManager`.

    Extends ``_JWTVerificationMixin`` so revocation results flow through
    the shared hook-emission plumbing. All public attributes referenced
    here are initialised by ``JWTTokenManager.__init__``; they are
    declared below as class-level annotations solely to satisfy static
    type checkers.
    """

    # ── Attributes set by JWTTokenManager.__init__ ───────────────────────────
    _blacklist_mgr: JWTBlacklist
    logger: Logger

    async def logout(self, token: str) -> Result[None, ContractsTokenError]:
        """Invalidate a token by adding it to the blacklist.

        When a ``cache_service`` is configured the token hash is stored in
        the cache with key ``jwt:blacklist:{sha256_hex}`` and a TTL equal to
        the token's remaining lifetime.  When no cache is configured the hash
        is stored in an in-process set (cleared on process restart).

        Args:
            token: The JWT token to invalidate.

        Returns:
            ``Ok(None)`` on success or if the token was already expired.
            ``Err(TokenError)`` if the cache write failed.

        Raises:
            RuntimeError: On cache-level infrastructure failures.
            OSError: On network-level failures.
            ConnectionError: On connection failures.
        """
        from quadkit.auth.hooks import AuthTokenRevokedHook

        result = await self._blacklist_mgr.revoke(token)
        if result.is_ok():
            try:
                payload = jwt.decode(
                    token,
                    options={
                        "verify_signature": False,
                        "verify_exp": False,
                        "verify_aud": False,
                    },
                )
            except (jwt.DecodeError, jwt.InvalidTokenError, ValueError, TypeError):
                self.logger.warning("jwt_logout_hook_payload_decode_failed")
            else:
                await self._emit_action(
                    "auth.logout",
                    AuthTokenRevokedHook(
                        user_id=str(payload.get("sub", "")),
                        token_type=str(payload.get("type", "access")),
                    ),
                )
        return result

    async def logout_all_user_tokens(
        self, user_id: str
    ) -> Result[None, ContractsTokenError]:
        """Invalidate all tokens for a user by writing a user-level blacklist entry.

        Args:
            user_id: The user ID to invalidate all tokens for.

        Returns:
            ``Ok(None)`` on success. ``Err(TokenError)`` if the cache write failed.

        Raises:
            RuntimeError: If no cache backend is configured.
        """
        return await self._blacklist_mgr.revoke_all_for_user(user_id)

    async def _is_token_blacklisted(self, token: str) -> bool:
        """Check if a token is blacklisted.

        Args:
            token: The JWT token to check.

        Returns:
            ``True`` if the token should be rejected, ``False`` otherwise.
        """
        return await self._blacklist_mgr.is_blacklisted(token)
