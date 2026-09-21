"""Convention followed: **Controller pattern** — stateless HTTP adapters.
This controller has no fallible path (the stats view is total), so its
handler returns a plain dict.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.web import Controller, get

if TYPE_CHECKING:
    from websocket_echo.services.rooms import ConnectionRegistry


class StatsController(Controller):
    """Report live room membership."""

    prefix = "/"

    def __init__(self, registry: ConnectionRegistry | None = None) -> None:
        self._registry = registry

    @get("/")
    async def index(self) -> dict[str, Any]:
        """Describe this demo's surface (the hub mounts it at ``/examples/<slug>/``)."""
        return {
            "demo": "websocket-echo",
            "summary": "Websocket echo with room membership and caps.",
            "endpoints": ["GET /stats", "WS /ws"],
        }

    @get("/stats")
    async def stats(self) -> dict[str, Any]:
        """Return the current connection count per room."""
        return {"rooms": dict(self._registry.counts)}


__all__ = ["StatsController"]
