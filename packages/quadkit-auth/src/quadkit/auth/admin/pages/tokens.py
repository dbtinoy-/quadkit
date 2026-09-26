"""Auth tokens management page — token key information."""

from __future__ import annotations

from typing import Any

from quadkit.auth.authn.jwt import JWTTokenManager
from quadkit.contracts.admin import PageContent
from quadkit.contracts.admin.widget_content import (
    EmptyContent,
    TableCell,
    TableContent,
)
from quadkit.logging import get_logger

logger = get_logger(__name__)


class AuthTokensPage:
    """Admin page displaying JWT token configuration and key info."""

    def __init__(
        self,
        token_manager: JWTTokenManager | None = None,
    ) -> None:
        self._token_manager = token_manager

    async def handle(self, request: Any) -> PageContent:
        if self._token_manager is None:
            return PageContent(
                title="Token Configuration",
                body=EmptyContent(
                    title="Token Manager Unavailable",
                    message="No JWT token manager is configured.",
                    icon="key",
                ),
            )

        try:
            keys_data = self._token_manager.list_keys()
            current_key_id = self._token_manager.current_key_id
        except Exception:
            logger.warning("auth_tokens.config_unavailable")
            return PageContent(
                title="Token Configuration",
                body=EmptyContent(
                    title="Token Configuration Unavailable",
                    message="Failed to read JWT token configuration.",
                    icon="alert-triangle",
                ),
            )

        rows = tuple(
            (
                TableCell(str(kid)),
                TableCell("Current" if kid == current_key_id else "Active"),
                TableCell(str(meta.get("created_at", "-"))),
            )
            for kid, meta in keys_data.items()
        )

        return PageContent(
            title="Token Configuration",
            body=TableContent(columns=("Key ID", "Status", "Created"), rows=rows),
        )
