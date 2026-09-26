"""Password-change service using the auth stack's composed hasher."""

from __future__ import annotations

from quadkit.auth.exceptions import (
    InvalidCredentialsError,
    PasswordPolicyError,
)
from quadkit.auth.models import UserCredentials
from quadkit.auth.storage import UserStoreProtocol
from quadkit.contracts.auth import (
    PasswordHasherProtocol,
    PasswordPolicyProtocol,
)
from quadkit.logging import get_logger
from quadkit.result import Err, Ok, Result

logger = get_logger(__name__)


class PasswordChangeService:
    """Change passwords through the framework's composed hasher.

    ``UserService.change_user_password`` verifies with a plain bcrypt hasher,
    which cannot read Argon2id hashes produced by the composed primary/legacy
    scheme. This service instead uses the exact hasher instance the
    authentication stack owns, so verify + rehash behave identically to login.

    Args:
        password_hasher: The authentication stack's composed hasher.
        policy: Password policy for validating the new password.
        user_store: The shared user store (credentials live here).
    """

    def __init__(
        self,
        password_hasher: PasswordHasherProtocol,
        policy: PasswordPolicyProtocol,
        user_store: UserStoreProtocol,
    ) -> None:
        self._hasher = password_hasher
        self._policy = policy
        self._store = user_store

    async def change(
        self, user_id: str, current_password: str, new_password: str
    ) -> Result[None, InvalidCredentialsError | PasswordPolicyError]:
        """Verify the current password, then store an updated hash.

        Args:
            user_id: Owning user.
            current_password: Plain-text current password.
            new_password: Replacement password (policy-checked).

        Returns:
            ``Ok(None)`` on success, ``Err(InvalidCredentialsError)`` for a
            wrong current password or unknown user, ``Err(PasswordPolicyError)``
            when the new password violates policy.
        """
        creds = await self._store.get_credentials(user_id)
        if not creds or not creds.hashed_password:
            # Same message as a wrong password: never leak existence.
            return Err(InvalidCredentialsError("Current password is incorrect"))
        if not await self._hasher.verify(current_password, creds.hashed_password):
            return Err(InvalidCredentialsError("Current password is incorrect"))

        try:
            self._policy.validate(new_password)
        except ValueError as exc:
            return Err(PasswordPolicyError(str(exc)))

        new_hash = await self._hasher.hash(new_password)
        await self._store.update_credentials(
            UserCredentials(
                user_id=user_id,
                hashed_password=new_hash,
                previous_hashes=[creds.hashed_password, *creds.previous_hashes],
            )
        )
        logger.info("password_changed", user_id=user_id)
        return Ok(None)


__all__ = ["PasswordChangeService"]
