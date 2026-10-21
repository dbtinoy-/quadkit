"""Authentication services for user login, registration, and token management."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from quadkit import serialization as _json
from quadkit.auth.authn.security import (
    DUMMY_PASSWORD_HASH,
    PasswordHasher,
    PasswordPolicy,
)
from quadkit.auth.events import (
    PasswordChanged,
    UserLockedOut,
    UserLoggedIn,
    UserLoginFailed,
    UserRegistered,
)
from quadkit.auth.exceptions import (
    AccountLockedError,
    EmailExistsError,
    InvalidCredentialsError,
    PasswordPolicyError,
)
from quadkit.auth.models.user import User, UserCredentials
from quadkit.auth.services.activity_tracker import AuthActivityTracker
from quadkit.contracts.auth.protocols import (
    LoginAttemptTrackerProtocol,
    PasswordHasherProtocol,
)
from quadkit.di.decorators import inject
from quadkit.logging import get_logger
from quadkit.primitives import clock as ambient_clock

if TYPE_CHECKING:
    from quadkit.auth.authn.jwt import JWTTokenManager
    from quadkit.auth.authn.schemas import RegisterRequest
    from quadkit.auth.models import AuthToken
    from quadkit.auth.storage.token_store import UserStoreProtocol
    from quadkit.contracts.auth.exceptions import TokenError
    from quadkit.contracts.auth.token import VerifiedToken
    from quadkit.contracts.core import HookRegistryProtocol
    from quadkit.contracts.events.protocols import EventBusProtocol
    from quadkit.contracts.infra.cache.protocols import CacheBackendProtocol
    from quadkit.result import Result

logger = get_logger(__name__)


@dataclass
class LockoutConfig:
    """Configuration for account lockout on repeated failed login attempts.

    Attributes:
        max_failed_attempts: Number of failed attempts within the observation
            window that triggers a lockout.  Defaults to 5.
        lockout_duration_seconds: Length of the rolling observation window in
            seconds.  The lockout is lifted automatically once all recorded
            failures fall outside this window.  Defaults to 300 (5 minutes).
        max_attempts: Canonical alias for ``max_failed_attempts``.  Both
            fields default to 5 and are kept in sync by ``__post_init__``.

    Note:
        For distributed deployments pass a ``CacheBackendProtocol`` to
        :class:`LoginAttemptTracker` instead of relying on the in-process
        dict managed by ``AuthenticationService``.
    """

    max_failed_attempts: int = 5
    lockout_duration_seconds: int = 300
    max_attempts: int = field(default=5)

    def __post_init__(self) -> None:
        # max_attempts is the canonical name; max_failed_attempts exists for
        # backward compatibility.  Sync rules:
        #   • If max_attempts was set to a non-default value → it wins.
        #   • Otherwise max_failed_attempts is the source of truth.
        if self.max_attempts != 5:
            self.max_failed_attempts = self.max_attempts
        else:
            self.max_attempts = self.max_failed_attempts


class LoginAttemptTracker(LoginAttemptTrackerProtocol):
    """Tracks failed login attempts and enforces account lockout.

    Supports both in-process state (no external dependency) and distributed
    state via an injected :class:`~quadkit.contracts.cache.protocols.CacheBackendProtocol`.
    When a cache backend is provided all attempt records are stored there so
    that multiple application instances share the same view — preventing an
    attacker from bypassing lockout by rotating across instances.

    Args:
        max_attempts: Consecutive failures within *lockout_duration_seconds*
            that trigger a lockout.  Defaults to 5.
        lockout_duration_seconds: Rolling window size **and** cache TTL.
            Defaults to 900 seconds (15 minutes).
        cache: Optional cache backend for distributed state.  When ``None``
            an in-process ``dict`` is used instead.

    Example::

        tracker = LoginAttemptTracker(max_attempts=5, lockout_duration_seconds=900)

        await tracker.record_failure("user@example.com")
        locked = await tracker.is_locked("user@example.com")  # False until 5 failures

        await tracker.clear("user@example.com")  # reset on successful login
    """

    _CACHE_KEY_PREFIX = "quadkit:auth:attempts:"

    def __init__(
        self,
        max_attempts: int = 5,
        lockout_duration_seconds: int = 900,
        cache: CacheBackendProtocol | None = None,
    ) -> None:
        self.max_attempts = max_attempts
        self.lockout_duration_seconds = lockout_duration_seconds
        self._cache = cache
        # In-memory fallback: identifier → list of monotonic timestamps
        self._local: dict[str, list[float]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def is_locked(self, identifier: str) -> bool:
        """Return ``True`` if *identifier* has exceeded the failure threshold.

        Args:
            identifier: Username, e-mail address, or IP used as the tracking key.
        """
        if self._cache is not None:
            return await self._is_locked_cache(identifier)
        return self._is_locked_local(identifier)

    async def record_failure(self, identifier: str) -> None:
        """Record a failed authentication attempt for *identifier*.

        Args:
            identifier: Username, e-mail address, or IP used as the tracking key.
        """
        if self._cache is not None:
            await self._record_failure_cache(identifier)
        else:
            self._record_failure_local(identifier)

    async def clear(self, identifier: str) -> None:
        """Remove all recorded failures for *identifier* (call on success).

        Args:
            identifier: Username, e-mail address, or IP used as the tracking key.
        """
        if self._cache is not None:
            await self._cache.delete(self._CACHE_KEY_PREFIX + identifier)
        else:
            self._local.pop(identifier, None)

    # ------------------------------------------------------------------
    # Cache-backed helpers
    # ------------------------------------------------------------------

    async def _is_locked_cache(self, identifier: str) -> bool:
        key = self._CACHE_KEY_PREFIX + identifier
        raw: Any = await self._cache.get(key)  # type: ignore[union-attr]
        if raw is None:
            return False
        data: dict[str, Any] = (
            _json.loads(raw) if isinstance(raw, (str, bytes)) else raw
        )
        now = ambient_clock.monotonic()
        window_start = now - self.lockout_duration_seconds
        recent = [t for t in data.get("timestamps", []) if t > window_start]
        return len(recent) >= self.max_attempts

    async def _record_failure_cache(self, identifier: str) -> None:
        key = self._CACHE_KEY_PREFIX + identifier
        raw: Any = await self._cache.get(key)  # type: ignore[union-attr]
        now = ambient_clock.monotonic()
        window_start = now - self.lockout_duration_seconds
        if raw is None:
            timestamps: list[float] = []
        else:
            data: dict[str, Any] = (
                _json.loads(raw) if isinstance(raw, (str, bytes)) else raw
            )
            timestamps = [t for t in data.get("timestamps", []) if t > window_start]
        timestamps.append(now)
        await self._cache.set(  # type: ignore[union-attr]
            key,
            _json.dumps({"timestamps": timestamps}),
            ttl=self.lockout_duration_seconds,
        )

    # ------------------------------------------------------------------
    # In-memory helpers
    # ------------------------------------------------------------------

    def _is_locked_local(self, identifier: str) -> bool:
        now = ambient_clock.monotonic()
        window_start = now - self.lockout_duration_seconds
        recent = [t for t in self._local.get(identifier, []) if t > window_start]
        return len(recent) >= self.max_attempts

    def _record_failure_local(self, identifier: str) -> None:
        now = ambient_clock.monotonic()
        window_start = now - self.lockout_duration_seconds
        existing = self._local.get(identifier, [])
        self._local[identifier] = [t for t in existing if t > window_start] + [now]


@inject
class AuthenticationService:
    """Service for core authentication operations.

    Handles user login, registration, token creation and validation.
    """

    def __init__(
        self,
        password_policy: PasswordPolicy,
        user_store: UserStoreProtocol,
        token_manager: JWTTokenManager,
        lockout_config: LockoutConfig | None = None,
        event_bus: EventBusProtocol | None = None,
        tracker: LoginAttemptTracker | None = None,
        hooks: HookRegistryProtocol | None = None,
        password_hasher: PasswordHasherProtocol | None = None,
        activity_tracker: AuthActivityTracker | None = None,
    ) -> None:
        self.password_policy = password_policy
        self.user_store = user_store
        self.token_manager = token_manager
        self.lockout_config: LockoutConfig = lockout_config or LockoutConfig()
        self._event_bus = event_bus
        # Use the explicitly supplied tracker, or build a default in-memory one
        # from lockout_config so callers that pre-date LoginAttemptTracker are
        # not affected.
        self._tracker: LoginAttemptTracker = tracker or LoginAttemptTracker(
            max_attempts=self.lockout_config.max_attempts,
            lockout_duration_seconds=self.lockout_config.lockout_duration_seconds,
        )
        self._hooks = hooks
        # The composed hasher injected by the provider; falls back to the
        # bcrypt hasher for callers that construct the service directly.
        self._password_hasher: PasswordHasherProtocol = (
            password_hasher or PasswordHasher()
        )
        # Tracks dashboard auth activity when bound by the DI container;
        # ``None`` disables recording (e.g. tests or bare constructions).
        self._activity_tracker = activity_tracker
        # Background tasks kept alive to prevent GC before completion
        self._background_tasks: set[asyncio.Task[object]] = set()

    def __repr__(self) -> str:
        """Return a string representation of this service."""
        return f"AuthenticationService(user_store={type(self.user_store).__name__})"

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

    def set_hook_registry(self, hooks: HookRegistryProtocol | None) -> None:
        """Attach an optional hook registry after provider boot wiring."""
        self._hooks = hooks

    async def _emit_action(self, hook_name: str, payload: object) -> None:
        """Emit an auth action hook when a registry is available."""
        if self._hooks is None:
            return

        await self._hooks.call_action(hook_name, payload=payload)

    async def authenticate_user(
        self,
        email: str,
        password: str,
    ) -> Result[User, InvalidCredentialsError | AccountLockedError]:
        """Authenticate a user with email and password.

        Always performs a password hash verification regardless of whether the
        user exists.  This constant-time behaviour prevents user-enumeration
        attacks via timing side-channels.

        If the account has exceeded ``LockoutConfig.max_attempts``
        within the observation window an ``AccountLockedError`` is returned
        immediately without performing credential verification.

        Returns:
            ``Ok(User)`` if authentication succeeds,
            ``Err(AccountLockedError)`` if the account is temporarily locked,
            ``Err(InvalidCredentialsError)`` otherwise.
        """
        from quadkit.result import Err, Ok

        # Lockout check — must happen before any credential work
        if await self._tracker.is_locked(email):
            # Best-effort user fetch to populate the richer UserLockedOut event.
            locked_user = await self.user_store.get_user_by_email(email)
            if locked_user:
                self._emit(UserLockedOut(user_id=locked_user.user_id, email=email))
            else:
                self._emit(UserLoginFailed(email=email, reason="Account locked"))
            if self._activity_tracker is not None:
                self._activity_tracker.record_failed_login()
            return Err(AccountLockedError(email))

        user = await self.user_store.get_user_by_email(email)

        # Resolve credentials separately — credentials are never stored on User.
        creds = await self.user_store.get_credentials(user.user_id) if user else None

        # Always verify against *some* hash so the code path takes constant
        # time whether the user exists or not.
        hashed = (
            creds.hashed_password
            if creds and creds.hashed_password
            else DUMMY_PASSWORD_HASH
        )
        verified = await self._password_hasher.verify(password, hashed)

        if user and user.is_active and verified:
            from quadkit.auth.hooks import AuthUserAuthenticatedHook

            # Successful login — clear failure history
            await self._tracker.clear(email)
            user.record_login()
            await self._rehash_password_if_needed(user, password, creds)
            self._emit(UserLoggedIn(user_id=user.user_id, email=user.email))
            await self._emit_action(
                "auth.login",
                AuthUserAuthenticatedHook(user_id=user.user_id, method="password"),
            )
            return Ok(user)

        # Record the failure
        await self._tracker.record_failure(email)
        self._emit(UserLoginFailed(email=email, reason="Invalid credentials"))
        if self._activity_tracker is not None:
            self._activity_tracker.record_failed_login()
        return Err(InvalidCredentialsError())

    async def change_user_password(
        self,
        user_id: str,
        current_password: str,
        new_password: str,
    ) -> Result[None, InvalidCredentialsError | PasswordPolicyError]:
        """Change a user's password after verifying the current password.

        This lives on ``AuthenticationService`` so applications that use the
        provider's composed password hasher keep the same Argon2id-default plus
        bcrypt-legacy behaviour for both login and password changes.
        """
        from quadkit.result import Err, Ok

        user = await self.user_store.get_user_by_id(user_id)
        creds = await self.user_store.get_credentials(user_id) if user else None
        if (
            not user
            or not user.is_active
            or not creds
            or not creds.hashed_password
            or not await self._password_hasher.verify(
                current_password, creds.hashed_password
            )
        ):
            return Err(InvalidCredentialsError("Current password is incorrect"))

        try:
            self.password_policy.validate(new_password)
        except ValueError as exc:
            return Err(PasswordPolicyError(str(exc)))

        if getattr(self.password_policy, "prevent_reuse", False):
            history_size = getattr(self.password_policy, "history_size", 5)
            recent_hashes = [
                value
                for value in [creds.hashed_password, *creds.previous_hashes]
                if value
            ]
            for old_hash in recent_hashes[: history_size + 1]:
                if await self._password_hasher.verify(new_password, old_hash):
                    return Err(
                        PasswordPolicyError(
                            "New password must not match recent passwords"
                        )
                    )

        new_hash = await self._password_hasher.hash(new_password)
        previous_hashes = (
            [creds.hashed_password, *creds.previous_hashes]
            if creds.hashed_password
            else list(creds.previous_hashes)
        )
        history_size = getattr(self.password_policy, "history_size", 5)
        previous_hashes = [value for value in previous_hashes if value][:history_size]
        await self.user_store.update_credentials(
            UserCredentials(
                user_id=user_id,
                hashed_password=new_hash,
                previous_hashes=previous_hashes,
            )
        )
        self._emit(PasswordChanged(user_id=user_id))
        return Ok(None)

    async def _rehash_password_if_needed(
        self,
        user: User,
        password: str,
        creds: UserCredentials | None,
    ) -> None:
        """Rehash password in background if needed."""
        if not creds or not creds.hashed_password:
            return

        try:
            new_hash = await self._password_hasher.rehash_if_needed(
                password,
                creds.hashed_password,
            )
            if new_hash:
                updated_creds = UserCredentials(
                    user_id=user.user_id,
                    hashed_password=new_hash,
                    previous_hashes=creds.previous_hashes,
                )
                await self.user_store.update_credentials(updated_creds)
        except Exception as exc:  # noqa: BLE001 — rehash is best-effort; login must not fail on it
            logger.warning("password_rehash_failed", reason=str(exc))

    async def register_user(
        self, request: RegisterRequest
    ) -> Result[User, EmailExistsError | PasswordPolicyError]:
        """Register a new user.

        Args:
            request: Registration request with email, name, and password.

        Returns:
            ``Ok(User)`` on success.
            ``Err(PasswordPolicyError)`` if passwords do not match or the
            password violates the policy.
            ``Err(EmailExistsError)`` if the email is already registered.
        """
        from quadkit.result import Err, Ok

        if request.password != request.confirm_password:
            return Err(PasswordPolicyError("Passwords do not match"))

        try:
            self.password_policy.validate(request.password)
        except ValueError as e:
            return Err(PasswordPolicyError(str(e)))

        if await self.user_store.get_user_by_email(request.email):
            return Err(EmailExistsError(request.email))

        hashed_password = await self._password_hasher.hash(request.password)

        user = await self.user_store.create_user(
            name=request.name,
            email=request.email,
            hashed_password=hashed_password,
            roles=["user"],
            profile=request.profile,
        )
        self._emit(UserRegistered(user_id=user.user_id, email=user.email))
        return Ok(user)

    def create_token(self, user: User) -> AuthToken:
        """Create an authentication token for a user."""
        return self.token_manager.create_token_pair(user)

    async def verify_token(self, token: str) -> Result[VerifiedToken, TokenError]:
        """Verify and decode an authentication token.

        Returns:
            ``Ok(VerifiedToken)`` if valid, ``Err(TokenError)`` otherwise.
        """
        return await self.token_manager.verify_token(token)

    async def refresh_token(self, refresh_token: str) -> Result[AuthToken, TokenError]:
        """Refresh an access token using a refresh token.

        Args:
            refresh_token: The refresh token string.

        Returns:
            ``Ok(AuthToken)`` if the refresh succeeds.
            ``Err(TokenError)`` if the refresh token is invalid or expired.
        """
        from quadkit.contracts.auth.exceptions import TokenError as _TokenError
        from quadkit.result import Err, Ok

        try:
            token = await self.token_manager.refresh_access_token(refresh_token)
            if self._activity_tracker is not None:
                self._activity_tracker.record_refresh()
            return Ok(token)
        except _TokenError as e:
            return Err(e)

    async def get_user_from_token(
        self, token: str
    ) -> Result[VerifiedToken, TokenError]:
        """Get user information from token.

        Returns:
            ``Ok(VerifiedToken)`` if valid, ``Err(TokenError)`` otherwise.
        """
        return await self.token_manager.get_user_from_token(token)

    async def shutdown(self) -> None:
        """Cancel and await all pending background event tasks."""
        tasks = list(self._background_tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._background_tasks.clear()


__all__ = ["AuthenticationService", "LockoutConfig", "LoginAttemptTracker"]
