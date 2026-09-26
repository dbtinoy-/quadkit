"""Password reset service for the auth web demo.

Wraps the framework's ``PasswordResetService`` with demo-specific behavior:
in-memory token storage and simulated email delivery (token returned in
the API response instead of actually sending an email).
"""

from __future__ import annotations

from datetime import datetime, timedelta

from auth_web.config import PasswordResetConfig
from quadkit.auth.storage import UserStoreProtocol
from quadkit.logging import get_logger
from quadkit.primitives import clock
from quadkit.result import Err, Ok, Result

logger = get_logger(__name__)


class PasswordResetError(Exception):
    """Error during password reset operations."""


class DemoPasswordResetService:
    """Demo password reset with in-memory token storage.

    In a real app, tokens would be emailed.  Here the token is returned
    in the API response so the test suite can exercise the full flow.
    """

    def __init__(
        self,
        user_store: UserStoreProtocol,
        config: PasswordResetConfig | None = None,
    ) -> None:
        self._store = user_store
        self._config = config or PasswordResetConfig()
        # token → (user_id, expiry)
        self._tokens: dict[str, tuple[str, datetime]] = {}

    async def request_reset(self, email: str) -> Result[str, PasswordResetError]:
        """Request a password reset.  Returns the reset token on success.

        ``Ok(token)`` when the user exists and a token was generated.
        ``Err(PasswordResetError)`` when no user with that email exists.
        """
        import secrets

        user = await self._store.get_user_by_email(email)
        if not user:
            logger.debug("password_reset_unknown_email", email=email)
            return Err(PasswordResetError("No account with that email"))

        token = secrets.token_urlsafe(self._config.token_length)
        expiry = clock.now() + timedelta(hours=self._config.token_expiry_hours)
        self._tokens[token] = (user.user_id, expiry)
        logger.info("password_reset_token_generated", user_id=user.user_id)
        return Ok(token)

    async def confirm_reset(
        self, token: str, new_password: str
    ) -> Result[None, PasswordResetError]:
        """Confirm password reset with a valid token.

        ``Ok(None)`` on success.
        ``Err(PasswordResetError)`` when the token is invalid or expired.
        """
        entry = self._tokens.get(token)
        if not entry:
            return Err(PasswordResetError("Invalid or expired reset token"))

        user_id, expiry = entry
        if clock.now() > expiry:
            del self._tokens[token]
            return Err(PasswordResetError("Invalid or expired reset token"))

        from quadkit.auth import PasswordHasher
        from quadkit.auth.models import UserCredentials

        hasher = PasswordHasher()
        hashed = await hasher.hash(new_password)

        creds = await self._store.get_credentials(user_id)
        await self._store.update_credentials(
            UserCredentials(
                user_id=user_id,
                hashed_password=hashed,
                previous_hashes=[creds.hashed_password]
                if creds and creds.hashed_password
                else [],
            )
        )
        del self._tokens[token]
        logger.info("password_reset_completed", user_id=user_id)
        return Ok(None)


__all__ = ["DemoPasswordResetService", "PasswordResetError"]
