"""Authentication service using Result pattern for error handling.

This service demonstrates the Result[T, AuthError] pattern for auth operations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from quadkit.auth.exceptions import InvalidCredentialsError, PasswordPolicyError
from quadkit.contracts.auth.exceptions import AuthError
from quadkit.logging import get_logger
from quadkit.result import Err, Ok, Result

if TYPE_CHECKING:
    from quadkit.auth.models.token import AuthToken
    from quadkit.contracts.events.protocols import EventBusProtocol
    from quadkit.contracts.infra.cache.protocols import CacheBackendProtocol

logger = get_logger(__name__)


class AuthServiceWithResultPattern:
    """Authentication service using Result pattern.

    This service wraps auth operations and returns Result[T, AuthError]
    instead of raising exceptions or returning bare types.
    """

    def __init__(
        self,
        cache: CacheBackendProtocol | None = None,
        event_bus: EventBusProtocol | None = None,
    ) -> None:
        """Initialize the auth service with optional dependencies.

        Args:
            cache: Cache backend for token validation
            event_bus: Event bus for auth events
        """
        self.cache = cache
        self.event_bus = event_bus

    async def validate_password(
        self,
        password: str,
        min_length: int = 8,
        require_uppercase: bool = True,
        require_digits: bool = True,
    ) -> Result[None, AuthError]:
        """Validate password against policy requirements.

        Args:
            password: Password to validate
            min_length: Minimum password length
            require_uppercase: Whether to require uppercase letters
            require_digits: Whether to require digits

        Returns:
            Ok(None) if valid, Err(PasswordPolicyError) if invalid
        """
        try:
            errors = []

            if len(password) < min_length:
                errors.append(f"Password must be at least {min_length} characters")

            if require_uppercase and not any(c.isupper() for c in password):
                errors.append("Password must contain uppercase letters")

            if require_digits and not any(c.isdigit() for c in password):
                errors.append("Password must contain digits")

            if errors:
                message = "; ".join(errors)
                return Err(PasswordPolicyError(message))

            return Ok(None)
        except Exception as e:  # noqa: BLE001  # demo service - broad catch for Result pattern demonstration
            logger.error("password_validation_failed: %s", e)
            return Err(AuthError(f"Password validation failed: {e}"))

    async def verify_credentials(
        self,
        username: str,
        password: str,
        stored_hash: str | None = None,
    ) -> Result[bool, AuthError]:
        """Verify user credentials against stored hash.

        Args:
            username: Username to verify
            password: Password to check
            stored_hash: Stored password hash (for demo purposes)

        Returns:
            Ok(True) if credentials valid, Err(InvalidCredentialsError) if not
        """
        try:
            if not username or not password:
                return Err(
                    InvalidCredentialsError("Username and password are required")
                )

            # Simple demo verification (replace with actual hash verification)
            if stored_hash is None:
                return Err(InvalidCredentialsError("No credentials on file for user"))

            # In production: use proper password hasher
            # password_valid = await self.password_hasher.verify(password, stored_hash)
            password_valid = password == stored_hash

            if not password_valid:
                return Err(InvalidCredentialsError("Invalid password"))

            return Ok(True)
        except Exception as e:  # noqa: BLE001  # demo service - broad catch for Result pattern demonstration
            logger.error("credential_verification_failed: %s", e)
            return Err(AuthError(f"Credential verification failed: {e}"))

    async def get_cached_token(
        self, token_id: str
    ) -> Result[AuthToken | None, AuthError]:
        """Get cached auth token.

        Args:
            token_id: Token identifier

        Returns:
            Ok(token) if found, Ok(None) if not found, Err(AuthError) on failure
        """
        try:
            if not self.cache:
                return Ok(None)

            cache_result = await self.cache.get(f"token:{token_id}")
            if cache_result.is_err():
                logger.warning("cache_get_failed: %s", cache_result.unwrap_err())
                return Ok(None)

            cached_data = cache_result.unwrap()
            if cached_data is None:
                return Ok(None)

            # In production: deserialize properly
            return Ok(cached_data)
        except Exception as e:  # noqa: BLE001  # demo service - broad catch for Result pattern demonstration
            logger.error("token_cache_retrieval_failed: %s", e)
            return Err(AuthError(f"Token retrieval failed: {e}"))

    async def cache_token(
        self,
        token_id: str,
        token: AuthToken,
        ttl: int = 3600,
    ) -> Result[None, AuthError]:
        """Cache auth token with TTL.

        Args:
            token_id: Token identifier
            token: Token to cache
            ttl: Time to live in seconds

        Returns:
            Ok(None) if successful, Err(AuthError) on failure
        """
        try:
            if not self.cache:
                return Ok(None)

            cache_result = await self.cache.set(
                f"token:{token_id}",
                token,
                ttl=ttl,
            )

            if cache_result.is_err():
                logger.warning("cache_set_failed: %s", cache_result.unwrap_err())
                return Err(AuthError("Failed to cache token"))

            return Ok(None)
        except Exception as e:  # noqa: BLE001  # demo service - broad catch for Result pattern demonstration
            logger.error("token_cache_failed: %s", e)
            return Err(AuthError(f"Token caching failed: {e}"))

    async def invalidate_token(self, token_id: str) -> Result[None, AuthError]:
        """Invalidate a cached token.

        Args:
            token_id: Token identifier to invalidate

        Returns:
            Ok(None) if successful, Err(AuthError) on failure
        """
        try:
            if not self.cache:
                return Ok(None)

            delete_result = await self.cache.delete(f"token:{token_id}")
            if delete_result.is_err():
                logger.warning("cache_delete_failed: %s", delete_result.unwrap_err())
                return Err(AuthError("Failed to invalidate token"))

            return Ok(None)
        except Exception as e:  # noqa: BLE001  # demo service - broad catch for Result pattern demonstration
            logger.error("token_invalidation_failed: %s", e)
            return Err(AuthError(f"Token invalidation failed: {e}"))


__all__ = ["AuthServiceWithResultPattern"]
