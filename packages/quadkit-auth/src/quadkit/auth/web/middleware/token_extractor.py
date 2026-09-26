"""Token extraction utilities for authentication middleware."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.auth import constants as const
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.contracts.web import RequestProtocol as Request

logger = get_logger(__name__)


class TokenExtractor:
    """Handles extraction of authentication tokens from HTTP requests."""

    def __init__(self, config: Any) -> None:
        """Initialize with middleware configuration.

        Args:
            config: AuthMiddlewareConfig with header_name, scheme, etc.
        """
        self.config = config

    def extract_token(self, request: Request) -> str | None:
        """Extract authentication token from request.

        Tries multiple sources in order:
        1. Authorization header
        2. Query parameter
        3. Cookie

        Args:
            request: HTTP request object

        Returns:
            Extracted token or None
        """
        # Try header first
        auth_header = request.headers.get(self.config.header_name)
        if isinstance(auth_header, str):
            # Log header presence (do not log full token for security)
            try:
                short_hdr = (
                    auth_header.split()[1][:10]
                    if len(auth_header.split()) > 1
                    else None
                )
            except (IndexError, TypeError):
                short_hdr = None
            logger.info(
                "TokenExtractor.extract_token: header present short=%s",
                short_hdr,
            )
            if auth_header.startswith(f"{self.config.scheme} "):
                return auth_header[len(f"{self.config.scheme} ") :]
            if auth_header.startswith("ApiKey "):
                return auth_header[7:]
            if (
                self.config.scheme.lower() == const.DEFAULT_TOKEN_TYPE.lower()
                and not auth_header.startswith(
                    f"{const.DEFAULT_TOKEN_TYPE} ",
                )
            ):
                # Allow bare tokens for Bearer scheme
                return auth_header

        # Try query parameter
        token = request.query_params.get("token")
        if isinstance(token, str):
            logger.info(
                "TokenExtractor.extract_token: token found in query (len=%d)",
                len(token),
            )
            return token

        # Try cookie
        token = request.cookies.get("access_token")
        if isinstance(token, str):
            logger.info(
                "TokenExtractor.extract_token: token found in cookie (len=%d)",
                len(token),
            )
            return token

        logger.debug("TokenExtractor.extract_token: no token found")
        return None


__all__ = ["TokenExtractor"]
