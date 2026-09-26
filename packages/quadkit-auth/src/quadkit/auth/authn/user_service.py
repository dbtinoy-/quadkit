"""User management services for CRUD operations."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, cast

from quadkit.auth.authn.security import PasswordHasher, PasswordPolicy
from quadkit.auth.events import PasswordChanged
from quadkit.auth.exceptions import (
    AuthorizationError,
    EmailExistsError,
    InvalidCredentialsError,
    PasswordPolicyError,
    UserNotFoundError,
)
from quadkit.auth.models.user import User, UserCredentials
from quadkit.contracts.exceptions import ValidationError
from quadkit.di.decorators import inject
from quadkit.logging import get_logger
from quadkit.result import Err, Ok, Result

if TYPE_CHECKING:
    from quadkit.contracts.events.protocols import EventBusProtocol

logger = get_logger(__name__)


@inject
class UserService:
    """Service for user management operations.

    Handles user CRUD, password management, and administrative operations.
    """

    def __init__(
        self,
        password_policy: PasswordPolicy,
        user_store: Any,
        event_bus: EventBusProtocol | None = None,
    ) -> None:
        self.password_policy = password_policy
        self.user_store = user_store
        self._event_bus = event_bus
        # Background tasks kept alive to prevent GC before completion
        self._background_tasks: set[asyncio.Task[object]] = set()

    def _emit(self, event: object) -> None:
        """Fire-and-forget event publication.

        Schedules a background task to publish *event* via the event bus (if
        one is configured).  The task reference is stored in
        ``_background_tasks`` to prevent premature garbage collection; it
        removes itself from the set upon completion.
        """
        if self._event_bus is None:
            return
        task: asyncio.Task[object] = asyncio.create_task(self._event_bus.publish(event))
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    async def create_user(
        self,
        name: str,
        email: str,
        password: str,
        roles: list[str] | None = None,
    ) -> Result[User, EmailExistsError | PasswordPolicyError]:
        """Create a new user.

        Returns:
            ``Ok(User)`` on success.
            ``Err(PasswordPolicyError)`` if the password does not satisfy policy.
            ``Err(EmailExistsError)`` if the email address is already registered.

        Infrastructure exceptions (e.g. DB connectivity) propagate unchanged.
        """
        try:
            self.password_policy.validate(password)
        except ValueError as e:
            return Err(PasswordPolicyError(str(e)))

        hashed_password = await PasswordHasher().hash(password)
        try:
            user = await self.user_store.create_user(
                name,
                email,
                hashed_password,
                roles,
            )
        except EmailExistsError as e:
            return Err(e)
        except ValueError as e:
            # In-memory store raises ValueError for duplicate email.
            return Err(EmailExistsError(str(e)))
        return Ok(user)

    async def get_user(self, user_id: str) -> User | None:
        """Get user by ID."""
        return cast("User | None", await self.user_store.get_user_by_id(user_id))

    async def update_user(
        self, user: User
    ) -> Result[User, UserNotFoundError | ValidationError]:
        """Update user information.

        Returns:
            ``Ok(User)`` on success.
            ``Err(UserNotFoundError)`` if the user does not exist.
            ``Err(ValidationError)`` if the supplied user data is invalid
                (e.g. empty email).

        Infrastructure exceptions (e.g. DB connectivity) propagate unchanged.
        """
        if not user.email:
            return Err(ValidationError("User email must not be empty"))
        existing = await self.user_store.get_user_by_id(user.user_id)
        if not existing:
            return Err(UserNotFoundError(user.user_id))
        await self.user_store.update_user(user)
        return Ok(user)

    async def delete_user(self, user_id: str) -> Result[None, UserNotFoundError]:
        """Delete a user.

        Returns:
            ``Ok(None)`` on success.
            ``Err(UserNotFoundError)`` if the user does not exist.

        Raises:
            AuthorizationError: If attempting to delete the protected ``admin``
                account (security boundary — not a recoverable Result path).

        Infrastructure exceptions (e.g. DB connectivity) propagate unchanged.
        """
        user = await self.get_user(user_id)
        if not user:
            return Err(UserNotFoundError(user_id))
        if user.name == "admin":
            raise AuthorizationError(
                "The system administrator account ('admin') cannot be deleted.",
            )
        await self.user_store.delete_user(user_id)
        return Ok(None)

    async def lock_user(self, user_id: str) -> Result[None, UserNotFoundError]:
        """Deactivate (lock) a user account.

        Sets ``is_active = False`` so the user cannot log in until unlocked.

        Returns:
            ``Ok(None)`` on success.
            ``Err(UserNotFoundError)`` if the user does not exist.

        Infrastructure exceptions propagate unchanged.
        """
        import dataclasses

        user = await self.get_user(user_id)
        if not user:
            return Err(UserNotFoundError(user_id))
        locked = dataclasses.replace(user, is_active=False)
        await self.user_store.update_user(locked)
        return Ok(None)

    async def unlock_user(self, user_id: str) -> Result[None, UserNotFoundError]:
        """Reactivate (unlock) a previously locked user account.

        Sets ``is_active = True`` so the user may log in again.

        Returns:
            ``Ok(None)`` on success.
            ``Err(UserNotFoundError)`` if the user does not exist.

        Infrastructure exceptions propagate unchanged.
        """
        import dataclasses

        user = await self.get_user(user_id)
        if not user:
            return Err(UserNotFoundError(user_id))
        unlocked = dataclasses.replace(user, is_active=True)
        await self.user_store.update_user(unlocked)
        return Ok(None)

    async def change_user_password(
        self,
        user_id: str,
        current_password: str,
        new_password: str,
    ) -> Result[None, InvalidCredentialsError | PasswordPolicyError]:
        """Change a user's password (requires current password).

        Returns:
            ``Ok(None)`` on success.
            ``Err(InvalidCredentialsError)`` if the current password is wrong or
                the user does not exist.
            ``Err(PasswordPolicyError)`` if the new password violates policy or
                has been used recently.

        Infrastructure exceptions (e.g. DB connectivity) propagate unchanged.
        """
        user = await self.get_user(user_id)
        if not user:
            # Return the same error as wrong password to avoid leaking user existence.
            return Err(InvalidCredentialsError("Current password is incorrect"))

        creds = await self.user_store.get_credentials(user_id)
        if (
            not creds
            or not creds.hashed_password
            or not await PasswordHasher().verify(
                current_password,
                creds.hashed_password,
            )
        ):
            return Err(InvalidCredentialsError("Current password is incorrect"))

        try:
            self.password_policy.validate(new_password)
        except ValueError as e:
            return Err(PasswordPolicyError(str(e)))

        if getattr(self.password_policy, "prevent_reuse", False):
            history_size = getattr(self.password_policy, "history_size", 5)
            checks = [h for h in [creds.hashed_password, *creds.previous_hashes] if h]
            for old_hash in checks[: history_size + 1]:
                if await PasswordHasher().verify(new_password, old_hash):
                    return Err(
                        PasswordPolicyError(
                            "New password must not match recent passwords",
                        )
                    )

        new_hash = await PasswordHasher().hash(new_password)
        new_prev = (
            [creds.hashed_password, *creds.previous_hashes]
            if creds.hashed_password
            else list(creds.previous_hashes)
        )
        history_size = getattr(self.password_policy, "history_size", 5)
        new_prev = list(filter(lambda h: h, new_prev))[:history_size]

        updated_creds = UserCredentials(
            user_id=user_id,
            hashed_password=new_hash,
            previous_hashes=new_prev,
        )
        await self.user_store.update_credentials(updated_creds)
        self._emit(PasswordChanged(user_id=user_id))
        return Ok(None)

    async def set_user_password(
        self,
        user_id: str,
        new_password: str,
        force: bool = False,
    ) -> None:
        """Set a user's password (admin operation)."""
        user = await self.get_user(user_id)
        if not user:
            raise ValueError("User not found")

        try:
            self.password_policy.validate(new_password)
        except ValueError as e:
            raise ValueError(f"Password policy violation: {e}") from e

        creds = await self.user_store.get_credentials(user_id)

        if not force and getattr(self.password_policy, "prevent_reuse", False):
            if creds:
                history_size = getattr(self.password_policy, "history_size", 5)
                checks = [
                    h for h in [creds.hashed_password, *creds.previous_hashes] if h
                ]
                for old_hash in checks[: history_size + 1]:
                    if await PasswordHasher().verify(new_password, old_hash):
                        raise PasswordPolicyError(
                            "New password must not match recent passwords",
                        )

        new_hash = await PasswordHasher().hash(new_password)
        if creds:
            new_prev = (
                [creds.hashed_password, *creds.previous_hashes]
                if creds.hashed_password
                else list(creds.previous_hashes)
            )
            history_size = getattr(self.password_policy, "history_size", 5)
            new_prev = list(filter(lambda h: h, new_prev))[:history_size]
        else:
            new_prev = []

        updated_creds = UserCredentials(
            user_id=user_id,
            hashed_password=new_hash,
            previous_hashes=new_prev,
        )
        await self.user_store.update_credentials(updated_creds)

    async def list_users(self, skip: int = 0, limit: int = 100) -> list[User]:
        """List users with pagination."""
        return cast("list[User]", await self.user_store.list_users(skip, limit))

    async def count_users(self) -> int:
        """Count total users."""
        return cast("int", await self.user_store.count_users())

    def __repr__(self) -> str:
        """Return a string representation of this service."""
        return f"UserService(user_store={type(self.user_store).__name__})"

    async def shutdown(self) -> None:
        """Cancel and await all pending background event tasks."""
        tasks = list(self._background_tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._background_tasks.clear()


__all__ = ["UserService"]
