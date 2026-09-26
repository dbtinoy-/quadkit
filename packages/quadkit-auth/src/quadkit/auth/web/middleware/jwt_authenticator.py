"""JWT token authentication component."""

from __future__ import annotations

from typing import Any

from quadkit.contracts import AuthProviderProtocol
from quadkit.logging import LoggerProtocol as Logger
from quadkit.logging import get_logger

logger = get_logger(__name__)


class JwtAuthenticator:
    """Handles JWT token validation and user resolution."""

    def __init__(
        self,
        auth_provider: AuthProviderProtocol,
        config: Any | None = None,
        logger: Logger | None = None,
    ) -> None:
        self.auth_provider = auth_provider
        from quadkit.auth.web.middleware.token_extractor import TokenExtractor

        self.token_extractor = TokenExtractor(
            config
            or type(
                "Config", (), {"header_name": "Authorization", "scheme": "Bearer"}
            )()
        )

        if logger is None:
            from quadkit.logging import get_logger

            logger = get_logger(__name__)
        self.logger = logger.bind(middleware="JwtAuthenticator")

    async def authenticate(self, request: Any) -> Any | None:
        """Validate JWT token from request and return user if valid."""
        token = self.token_extractor.extract_token(request)
        if not token:
            return None

        try:
            token_result = await self.auth_provider.verify_token(token)
        except Exception as e:  # noqa: BLE001 — any verification failure rejects the request (None), never crashes the middleware
            self.logger.exception(
                "Unexpected error during JWT authentication",
                exc_info=e,
            )
            return None

        if token_result is None or token_result.is_err():
            self.logger.info(
                "JWT verification failed: %s",
                token_result.unwrap_err() if token_result is not None else "no result",
            )
            return None

        verified = token_result.unwrap()
        user_id = verified.user_id
        if not user_id:
            return None

        # Fetch fresh user data from store
        user = await self.auth_provider.get_user(user_id)
        if not user:
            return None

        # Pre-fetch delegations for sync check_access
        if self.auth_provider.delegation_manager:
            request.state.delegations = (
                await self.auth_provider.delegation_manager.get_active_delegations(
                    user.user_id,
                )
            )

        return user


__all__ = [
    "JwtAuthenticator",
    "logger",
]
