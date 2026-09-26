"""Refresh-token rotation seam for :class:`~quadkit.auth.authn.jwt.JWTTokenManager`.

This module is an internal implementation detail; import
:class:`~quadkit.auth.authn.jwt.JWTTokenManager` directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import jwt

from quadkit.auth.authn._jwt_revocation import _JWTRevocationMixin
from quadkit.auth.models import AuthToken
from quadkit.auth.models.user import User
from quadkit.contracts.auth.exceptions import TokenError as ContractsTokenError

if TYPE_CHECKING:
    from quadkit.auth.types import TokenPair
    from quadkit.contracts.auth.token import VerifiedToken
    from quadkit.logging import LoggerProtocol as Logger
    from quadkit.result import Result


class _JWTRefreshMixin(_JWTRevocationMixin):
    """Mixin providing refresh-token rotation for :class:`JWTTokenManager`.

    Extends the revocation seam (which itself extends verification), so
    refresh flows reuse verification, hook emission, and blacklist
    plumbing. All public attributes referenced here are initialised by
    ``JWTTokenManager.__init__``; they are declared below as class-level
    annotations solely to satisfy static type checkers.
    """

    # ── Attributes set by JWTTokenManager.__init__ ───────────────────────────
    logger: Logger

    def create_token_pair(  # pragma: no cover
        self,
        user: User,
        additional_claims: dict[str, Any] | None = None,
        binding_context: dict[str, str] | None = None,
    ) -> AuthToken:
        """Create token pair — provided by _JWTCreationMixin."""
        raise NotImplementedError

    async def refresh_token(
        self, refresh_token: str
    ) -> Result[AuthToken, ContractsTokenError]:
        """Refresh an access token using a refresh token.

        Delegates to :meth:`refresh_access_token`.  Satisfies the updated
        ``TokenManagerProtocol`` protocol from ``quadkit.contracts.auth.token``.

        Args:
            refresh_token: The refresh token string.

        Returns:
            ``Ok(AuthToken)`` if the refresh token is valid, or
            ``Err(TokenError)`` for expected domain failures
            (expired, blacklisted, invalid).
        """
        from quadkit.auth.exceptions import (
            BlacklistedTokenError,
            TokenBlacklistedError,
        )
        from quadkit.auth.exceptions import TokenError as AuthTokenError
        from quadkit.result import Err, Ok

        try:
            return Ok(await self.refresh_access_token(refresh_token))
        except BlacklistedTokenError as e:
            return Err(TokenBlacklistedError(str(e)))  # type: ignore[arg-type]
        except AuthTokenError as e:
            return Err(ContractsTokenError(str(e)))

    async def refresh_with_rotation(
        self, refresh_token: str
    ) -> Result[TokenPair, ContractsTokenError]:
        """Rotate a refresh token and return a new access + refresh token pair.

        Implements one-time-use refresh token rotation (RTR).  The incoming
        refresh token is verified, immediately blacklisted, and a fresh token
        pair is issued.  If the token is already blacklisted (reuse-attack
        vector), all sessions for the affected user are revoked and the call
        returns ``Err``.

        Args:
            refresh_token: The current refresh token JWT string to exchange.

        Returns:
            ``Ok(TokenPair)`` with fresh ``access`` and ``refresh`` tokens on
            success, or ``Err(ContractsTokenError)`` for any expected domain
            failure (expired, invalid signature, already revoked).

        Raises:
            RuntimeError: On cache / infrastructure failures.
            OSError: On network-level failures.
            ConnectionError: On connection failures.
        """
        from quadkit.auth.exceptions import (
            BlacklistedTokenError,
            TokenBlacklistedError,
        )
        from quadkit.auth.exceptions import TokenError as AuthTokenError
        from quadkit.auth.types import TokenPair
        from quadkit.result import Err, Ok

        try:
            auth_token = await self.refresh_access_token(refresh_token)
            return Ok(
                TokenPair(
                    access=auth_token.token,
                    refresh=auth_token.refresh_token or "",
                )
            )
        except BlacklistedTokenError as e:
            return Err(TokenBlacklistedError(str(e)))  # type: ignore[arg-type]
        except AuthTokenError as e:
            return Err(ContractsTokenError(str(e)))

    async def refresh_access_token(self, refresh_token: str) -> AuthToken:
        """Create new access token from refresh token with rotation.

        Implements one-time-use refresh tokens (RTR). The used refresh token is
        blacklisted and a new refresh token is issued.

        If a blacklisted refresh token is presented, it indicates a potential
        reuse attack. In this case, all tokens for the user are invalidated
        immediately to prevent further compromise.

        Raises:
            TokenBlacklistedError: If token reuse is detected (domain failure).
            TokenError: For other domain failures (expired, invalid).
            RuntimeError: On infrastructure failures (cache, network).
        """
        from quadkit.auth.exceptions import (
            BlacklistedTokenError,
            TokenBlacklistedError,
        )
        from quadkit.auth.exceptions import TokenError as AuthTokenError

        result = await self.verify_token(refresh_token, "refresh")
        if result.is_err():
            error = result.unwrap_err()
            if isinstance(error, TokenBlacklistedError):
                # TOKEN REUSE DETECTED!
                # If we try to use a blacklisted refresh token, someone might have stolen it.
                # Invalidate EVERYTHING for this user.
                try:
                    unverified_payload = jwt.decode(
                        refresh_token, options={"verify_signature": False}
                    )
                    user_id = unverified_payload.get("sub")
                    if user_id:
                        self.logger.warning(
                            "Refresh token reuse detected for user %s. Revoking all sessions.",
                            user_id,
                        )
                        await self.logout_all_user_tokens(user_id)
                except Exception:  # noqa: BLE001 — revocation is best-effort; the BlacklistedTokenError below must still be raised
                    self.logger.exception(
                        "Failed to revoke user tokens after reuse detection",
                    )
                except (jwt.DecodeError, jwt.InvalidTokenError, ValueError, KeyError):
                    self.logger.exception(
                        "Unexpected error during session revocation",
                    )
                raise BlacklistedTokenError(
                    "Refresh token reuse detected. All sessions revoked.",
                ) from None
            # Other domain errors (expired, invalid)
            raise AuthTokenError(str(error)) from error

        verified = result.unwrap()

        # Blacklist the used refresh token (rotation)
        await self.logout(refresh_token)

        # Create new token pair from token claims
        user = User(
            user_id=verified.user_id,
            name=verified.name,
            email=verified.email,
            roles=verified.roles,
            permissions=verified.permissions,
        )

        from quadkit.auth.hooks import AuthTokenRefreshedHook

        token_pair = self.create_token_pair(user)
        await self._emit_action(
            "token.refreshed",
            AuthTokenRefreshedHook(user_id=verified.user_id, token_type="access"),  # noqa: S106  # token KIND string, not a credential
        )
        return token_pair

    async def get_user_from_token(
        self, token: str
    ) -> Result[VerifiedToken, ContractsTokenError]:
        """Extract user information from access token.

        Returns:
            ``Ok(VerifiedToken)`` if the token is a valid access token, or
            ``Err(TokenError)`` for expected domain failures.
        """
        return await self.verify_token(token, "access")
