"""Convention followed: **Controller pattern** — stateless HTTP adapters.
The provider constructs the controller at boot with its dependencies and
rebinds it in the container; handlers stay trivial and delegate to the
service.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.web import Controller, get, post

if TYPE_CHECKING:
    from cache_side.services.report import ReportService


class ReportController(Controller):
    """Three routes: describe the demo, read the cached report, invalidate it."""

    prefix = "/"

    def __init__(self, service: ReportService | None = None) -> None:
        self._service = service

    @get("/")
    async def index(self) -> dict[str, Any]:
        """Describe this demo's surface (the hub mounts it at ``/examples/<slug>/``)."""
        return {
            "demo": "cache-aside",
            "summary": "Cache-aside reads through quadkit-cache: compute once, serve cached.",
            "endpoints": ["GET /report", "POST /report/invalidate"],
        }

    @get("/report")
    async def report(self) -> dict[str, Any]:
        """Return the report; ``cached`` reports whether this was a cache hit."""
        assert self._service is not None
        return await self._service.get_report()

    @post("/report/invalidate")
    async def invalidate(self) -> dict[str, Any]:
        """Drop the cached report so the next read recomputes."""
        assert self._service is not None
        await self._service.invalidate()
        return {"invalidated": True}


__all__ = ["ReportController"]
