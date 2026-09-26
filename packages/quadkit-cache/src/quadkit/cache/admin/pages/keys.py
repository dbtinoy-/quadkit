from __future__ import annotations

from typing import Any

from quadkit.contracts.admin import PageContent
from quadkit.contracts.admin.widget_content import EmptyContent


class CacheKeysPage:
    """Key browser for /admin/cache/keys."""

    async def handle(self, request: Any) -> PageContent:
        return PageContent(
            title="Cache Keys",
            body=EmptyContent(
                title="No Keys Displayed",
                message=(
                    "Key enumeration is not supported by the current cache "
                    "backend. Use the Flush Cache action to clear all keys."
                ),
                icon="key",
            ),
        )
