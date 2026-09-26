"""Account verification service for Quadkit Auth."""

from __future__ import annotations

from datetime import datetime, timedelta
import hmac
import secrets
from typing import TYPE_CHECKING, Any

from quadkit.auth.exceptions import AlreadyVerifiedError, UserNotFoundError
from quadkit.di.decorators import inject
from quadkit.logging import get_logger
from quadkit.primitives import clock as ambient_clock
from quadkit.result import Err, Ok, Result

if TYPE_CHECKING:
    from quadkit.auth.storage.token_store import UserStoreProtocol
    from quadkit.contracts.auth.exceptions import (
        VerificationError as ContractsVerificationError,
    )

logger = get_logger(__name__)


class AccountVerificationError(Exception):
    """Error during account verification operations."""

    _code = "QK_ERR_AUTH_027"


@inject
class AccountVerificationService:
    """Service for handling account verification flows.

    Provides email verification with time-limited tokens.
    """

    TOKEN_EXPIRY_DAYS = 7
    TOKEN_LENGTH = 32

    def __init__(
        self,
        user_store: UserStoreProtocol,
        token_ttl_days: int = TOKEN_EXPIRY_DAYS,
    ) -> None:
        self._store = user_store
        self._token_ttl = timedelta(days=token_ttl_days)

    def generate_verification_token(self) -> tuple[str, datetime]:
        """Generate a secure random verification token.

        Returns:
            Tuple of (token, expiry_datetime)
        """
        token = secrets.token_urlsafe(self.TOKEN_LENGTH)
        expiry = (ambient_clock.now()) + self._token_ttl
        return token, expiry

    async def send_verification(
        self, user_id: str
    ) -> Result[tuple[str, datetime], AlreadyVerifiedError | UserNotFoundError]:
        """Send verification email for a user.

        Args:
            user_id: The user's ID.

        Returns:
            Ok((token, expiry)) if the verification token was generated.
            Err(UserNotFoundError) if the user does not exist.
            Err(AlreadyVerifiedError) if the user is already verified.
        """
        user = await self._store.get_user_by_id(user_id)

        if not user:
            logger.debug("Verification requested for non-existent user: %s", user_id)
            return Err(UserNotFoundError(user_id))

        if getattr(user, "is_verified", False):
            logger.debug("User already verified: %s", user_id)
            return Err(AlreadyVerifiedError(user_id))

        token, expiry = self.generate_verification_token()

        user.verification_token = token  # type: ignore[attr-defined]
        user.verification_expires_at = expiry  # type: ignore[attr-defined]

        await self._store.update_user(user)

        logger.info("Verification token generated for user: %s", user_id)
        return Ok((token, expiry))

    async def verify(self, token: str) -> Result[None, ContractsVerificationError]:
        """Verify user account with token.

        Args:
            token: The verification token.

        Returns:
            Ok(None) if verification succeeded.
            Err(VerificationError) if the token is invalid or expired.
        """
        from quadkit.contracts.auth.exceptions import VerificationError as VErr

        user = await self._find_user_by_token(token)

        if not user:
            logger.warning("Invalid verification token used")
            return Err(VErr("Invalid or expired verification token"))

        user.is_verified = True
        user.verification_token = None
        user.verification_expires_at = None

        await self._store.update_user(user)

        logger.info("Account verified for user: %s", user.user_id)
        return Ok(None)

    async def _find_user_by_token(self, token: str) -> Any | None:
        """Find user by verification token."""
        users = await self._store.list_users(skip=0, limit=1000)

        for user in users:
            if (
                hasattr(user, "verification_token")
                and user.verification_token is not None
                and hmac.compare_digest(user.verification_token, token)
            ):
                if hasattr(user, "verification_expires_at") and (
                    user.verification_expires_at
                    and user.verification_expires_at > (ambient_clock.now())
                ):
                    return user
                break

        return None

    async def resend_verification(
        self, email: str
    ) -> Result[tuple[str, datetime], AlreadyVerifiedError | UserNotFoundError]:
        """Resend verification token.

        Args:
            email: The user's email.

        Returns:
            Ok((token, expiry)) if notified successfully.
            Err(UserNotFoundError) if the email is not registered.
            Err(AlreadyVerifiedError) if the user is already verified.
        """
        user = await self._store.get_user_by_email(email)

        if not user:
            return Err(UserNotFoundError(email))

        if getattr(user, "is_verified", False):
            return Err(AlreadyVerifiedError(user.user_id))

        return await self.send_verification(user.user_id)

    def __repr__(self) -> str:
        return f"AccountVerificationService(user_store={type(self._store).__name__})"


__all__ = [
    "AccountVerificationError",
    "AccountVerificationService",
    "logger",
]
