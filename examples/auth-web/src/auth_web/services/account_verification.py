"""Account verification service for the auth web demo.

Wraps the framework's verification concepts with demo-specific behavior:
in-memory token storage and simulated email delivery (token returned in
the API response instead of actually sending an email).
"""

from __future__ import annotations

from datetime import datetime, timedelta

from auth_web.config import AccountVerificationConfig
from quadkit.auth.storage import UserStoreProtocol
from quadkit.logging import get_logger
from quadkit.primitives import clock
from quadkit.result import Err, Ok, Result

logger = get_logger(__name__)


class AccountVerificationError(Exception):
    """Error during account verification operations."""


class DemoAccountVerificationService:
    """Demo account verification with in-memory token storage.

    In a real app, tokens would be emailed.  Here the token is returned
    in the API response so the test suite can exercise the full flow.
    """

    def __init__(
        self,
        user_store: UserStoreProtocol,
        config: AccountVerificationConfig | None = None,
    ) -> None:
        self._store = user_store
        self._config = config or AccountVerificationConfig()
        # token → (user_id, expiry)
        self._tokens: dict[str, tuple[str, datetime]] = {}

    async def send_verification(
        self, user_id: str
    ) -> Result[str, AccountVerificationError]:
        """Generate a verification token for the given user.

        ``Ok(token)`` on success.
        ``Err(AccountVerificationError)`` when the user is not found.
        """
        import secrets

        user = await self._store.get_user_by_id(user_id)
        if not user:
            return Err(AccountVerificationError("User not found"))

        if getattr(user, "is_verified", False):
            return Err(AccountVerificationError("User already verified"))

        token = secrets.token_urlsafe(self._config.token_length)
        expiry = clock.now() + timedelta(days=self._config.token_expiry_days)
        self._tokens[token] = (user_id, expiry)
        logger.info("verification_token_generated", user_id=user_id)
        return Ok(token)

    async def verify(self, token: str) -> Result[None, AccountVerificationError]:
        """Verify an account with a valid token.

        ``Ok(None)`` on success.
        ``Err(AccountVerificationError)`` when the token is invalid or expired.
        """
        entry = self._tokens.get(token)
        if not entry:
            return Err(
                AccountVerificationError("Invalid or expired verification token")
            )

        user_id, expiry = entry
        if clock.now() > expiry:
            del self._tokens[token]
            return Err(
                AccountVerificationError("Invalid or expired verification token")
            )

        user = await self._store.get_user_by_id(user_id)
        if not user:
            return Err(AccountVerificationError("User not found"))

        user.is_verified = True  # type: ignore[attr-defined]
        await self._store.update_user(user)
        del self._tokens[token]
        logger.info("account_verified", user_id=user_id)
        return Ok(None)

    async def is_verified(self, user_id: str) -> bool:
        """Check if a user's email is verified."""
        user = await self._store.get_user_by_id(user_id)
        if not user:
            return False
        return bool(getattr(user, "is_verified", False))


__all__ = ["AccountVerificationError", "DemoAccountVerificationService"]
