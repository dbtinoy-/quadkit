"""Server lifecycle management"""

from __future__ import annotations

from typing import Any

from quadkit.web.config import ServerConfig


class ServerLifecycle:
    """Manages server startup and shutdown lifecycle"""

    def __init__(self, config: ServerConfig):
        self.config = config
        self.server: Any | None = None

    async def start(self) -> None:
        """Start the server (handled by quadkit in pass-through mode)"""
        # In pass-through architecture, quadkit handles server lifecycle

    async def stop(self) -> None:
        """Stop the server"""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
